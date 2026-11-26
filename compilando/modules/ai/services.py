"""Contexto acotado, límites persistentes y reserva atómica antes de consultar IA."""

import json
from uuid import uuid4

from flask import abort, current_app
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import NotFound

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


from compilando.extensions import db
from compilando.modules.ai.models import SolicitudIA
from compilando.modules.ai.providers import ErrorIA, Gemini, ProveedorIA
from compilando.modules.answers.models import Respuesta
from compilando.modules.auth.security import limitar_intentos
from compilando.modules.auth.sessions import ahora_utc
from compilando.modules.questions.attachments import leer_adjunto
from compilando.modules.questions.models import Pregunta
from compilando.modules.questions.services import normalizar_nombre


def proveedor_actual() -> ProveedorIA:
    # Las pruebas inyectan un proveedor; en la aplicación siempre se usa Gemini real.
    proveedor = current_app.extensions.get("ai_provider")
    if proveedor is not None:
        return proveedor
    config = current_app.config
    clave = config["GEMINI_API_KEY"].strip()
    if not clave:
        raise ErrorIA("La IA todavía no está configurada. Avisale al equipo.")
    return Gemini(
        clave=clave,
        modelo=config["GEMINI_MODEL"],
        timeout=config["AI_TIMEOUT_SECONDS"],
        max_tokens=config["AI_MAX_OUTPUT_TOKENS"],
    )


def preparar_contexto(pregunta: Pregunta, incluir_adjuntos: bool) -> str:
    limite = current_app.config["AI_MAX_CONTEXT_BYTES"]
    archivos = []
    if incluir_adjuntos:
        if sum(a.tamanio for a in pregunta.adjuntos) > limite:
            raise ErrorIA(
                "Los adjuntos superan los 48 KB para consultar IA. "
                "Consultá sin adjuntos o compartí un ejemplo más pequeño.",
                400,
            )
        for adjunto in pregunta.adjuntos:
            try:
                codigo = leer_adjunto(adjunto)
            except NotFound:
                raise ErrorIA(
                    "No pudimos leer uno de los adjuntos. "
                    "Consultá sin adjuntos o avisale al equipo.",
                    400,
                ) from None
            archivos.append({"nombre": adjunto.nombre_original, "codigo": codigo})
    contexto = json.dumps(
        {"titulo": pregunta.titulo, "pregunta": pregunta.cuerpo_detallado, "archivos": archivos},
        ensure_ascii=False,
    )
    if len(contexto.encode("utf-8")) > limite:
        raise ErrorIA(
            "La pregunta y sus adjuntos superan los 48 KB para consultar IA. "
            "Reducí el ejemplo o consultá sin adjuntos.",
            400,
        )
    return contexto


def consultar_ia(
    pregunta_id: int,
    solicitante_id: int,
    incluir_adjuntos: bool,
    *,
    aplicar_limite: bool = True,
) -> Respuesta:
    pregunta = db.session.get(Pregunta, pregunta_id)
    if pregunta is None:
        abort(404)
    existente = db.session.scalar(
        select(Respuesta).where(Respuesta.pregunta_id == pregunta_id, Respuesta.es_ia.is_(True))
    )
    if existente is not None:
        return existente
    proveedor = proveedor_actual()
    contexto = preparar_contexto(pregunta, incluir_adjuntos)
    ahora = ahora_utc()
    actual = db.session.get(SolicitudIA, pregunta_id)
    if actual and actual.estado == "pendiente" and actual.vence > ahora:
        raise ErrorIA("Ya se está preparando una respuesta. Esperá y recargá la pregunta.", 409)
    # También cuentan los intentos fallidos; los duplicados no hacen otra llamada a Gemini.
    if aplicar_limite:
        limitar_intentos("ai", usuario_id=solicitante_id)
    token = uuid4().hex
    valores = {
        "solicitante_id": solicitante_id,
        "token": token,
        "estado": "pendiente",
        "vence": ahora + current_app.config["AI_REQUEST_LIFETIME"],
    }
    try:
        reservado = db.session.execute(
            update(SolicitudIA)
            .where(
                SolicitudIA.pregunta_id == pregunta_id,
                or_(SolicitudIA.estado == "error", SolicitudIA.vence <= ahora),
                SolicitudIA.respuesta_id.is_(None),
            )
            .values(**valores)
        ).rowcount
        if not reservado:
            db.session.add(SolicitudIA(pregunta_id=pregunta_id, **valores))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErrorIA(
            "Otra consulta ya está en curso. Recargá la pregunta en unos segundos.", 409
        ) from None
    # No mantenemos una transacción abierta mientras esperamos al proveedor externo.
    try:
        texto = proveedor.responder(contexto)
        if not isinstance(texto, str) or not 3 <= len(texto.strip()) <= 20000:
            raise ErrorIA("La IA no devolvió una respuesta utilizable. Volvé a intentarlo.")
        vigente = db.session.execute(
            update(SolicitudIA)
            .where(
                SolicitudIA.pregunta_id == pregunta_id,
                SolicitudIA.token == token,
                SolicitudIA.estado == "pendiente",
                SolicitudIA.vence > ahora_utc(),
            )
            .values(estado="completada")
        ).rowcount
        if not vigente:
            raise ErrorIA(
                "La consulta venció. Recargá la pregunta antes de volver a intentar.", 409
            )
        respuesta = Respuesta(
            cuerpo=texto.strip(),
            pregunta_id=pregunta_id,
            usuario_id=None,
            es_ia=True,
            proveedor_ia=proveedor.nombre,
            modelo_ia=proveedor.modelo,
        )
        db.session.add(respuesta)
        db.session.flush()
        db.session.execute(
            update(SolicitudIA)
            .where(SolicitudIA.pregunta_id == pregunta_id, SolicitudIA.token == token)
            .values(respuesta_id=respuesta.id)
        )
        db.session.commit()
        return respuesta
    except Exception:
        db.session.rollback()
        db.session.execute(
            update(SolicitudIA)
            .where(SolicitudIA.pregunta_id == pregunta_id, SolicitudIA.token == token)
            .values(estado="error")
        )
        db.session.commit()
        raise

@dataclass(frozen=True)
class DeteccionIA:
    requiere: bool
    motivo: str | None = None


def detectar_pregunta_requiere_ia(
    pregunta: Pregunta,
    *,
    cantidad_respuestas: int | None = None,
    tiene_respuesta_ia: bool | None = None,
    ahora: datetime | None = None,
) -> DeteccionIA:
    """Detecta si una pregunta requiere IA por etiqueta o por tiempo sin respuestas."""

    if tiene_respuesta_ia is None:
        tiene_respuesta_ia = any(r.es_ia for r in pregunta.respuestas)
    if tiene_respuesta_ia:
        return DeteccionIA(requiere=False, motivo=None)

    etiquetas_ia = {
        normalizar_nombre(tag)
        for tag in current_app.config.get("AI_TRIGGER_TAGS", ("ia", "ai", "gemini", "asistente-ia"))
    }
    if any(normalizar_nombre(tag.nombre) in etiquetas_ia for tag in pregunta.tags):
        return DeteccionIA(requiere=True, motivo="etiqueta")

    if cantidad_respuestas is None:
        cantidad_respuestas = len(pregunta.respuestas)

    if cantidad_respuestas == 0 and pregunta.fecha is not None:
        minutos_espera = int(current_app.config.get("AI_UNANSWERED_MINUTES", 1440))
        tz_ar = ZoneInfo("America/Argentina/Buenos_Aires")
        referencia = (ahora or datetime.now(tz_ar)).replace(tzinfo=None)
        if isinstance(pregunta.fecha, datetime):
            fecha_pregunta = pregunta.fecha.replace(tzinfo=None)
        else:
            fecha_pregunta = datetime.combine(pregunta.fecha, time.min)
        if referencia - fecha_pregunta >= timedelta(minutes=minutos_espera):
            return DeteccionIA(requiere=True, motivo="tiempo_sin_respuesta")


    return DeteccionIA(requiere=False, motivo=None)



def listar_preguntas_requieren_ia() -> list[tuple[Pregunta, DeteccionIA]]:
    """Devuelve todas las preguntas publicadas que cumplen algún criterio para IA."""
    preguntas = db.session.scalars(
        select(Pregunta).order_by(Pregunta.fecha.desc(), Pregunta.id.desc())
    ).all()
    resultado: list[tuple[Pregunta, DeteccionIA]] = []
    for pregunta in preguntas:
        deteccion = detectar_pregunta_requiere_ia(pregunta)
        if deteccion.requiere:
            resultado.append((pregunta, deteccion))
    return resultado



def responder_automaticamente_si_vencio(pregunta: Pregunta) -> Respuesta | None:
    if current_app.config.get("TESTING") and not current_app.config.get("AI_AUTO_RESPOND_IN_TESTS"):
        return None  # (o return 0 en procesar_preguntas_vencidas_ia)
    """Genera una respuesta de IA automáticamente si la pregunta venció el tiempo sin respuestas."""
    if not current_app.config.get("AI_AUTO_RESPOND_UNANSWERED", False):
        return None
    if pregunta.usuario_id is None:
        return None

    deteccion = detectar_pregunta_requiere_ia(pregunta)
    if not deteccion.requiere or deteccion.motivo != "tiempo_sin_respuesta":
        return None

    try:
        return consultar_ia(
            pregunta_id=pregunta.id,
            solicitante_id=pregunta.usuario_id,
            incluir_adjuntos=False,
            aplicar_limite=False,
        )
    except Exception:
        current_app.logger.warning(
            "No se pudo generar la respuesta automática de IA para la pregunta %s.",
            pregunta.id,
        )
        return None


def procesar_preguntas_vencidas_ia(limite: int = 5) -> int:
    """Busca preguntas sin respuestas que superaron el tiempo configurado y les genera respuesta IA."""
    if not current_app.config.get("AI_AUTO_RESPOND_UNANSWERED", False):
        return 0
    if current_app.config.get("TESTING") and not current_app.config.get("AI_AUTO_RESPOND_IN_TESTS"):
     return 0  # (o return 0 en procesar_preguntas_vencidas_ia)
    
    preguntas_sin_respuestas = db.session.scalars(
        select(Pregunta)
        .where(~Pregunta.respuestas.any())
        .order_by(Pregunta.fecha.asc(), Pregunta.id.asc())
        .limit(limite * 4)
    ).all()

    generadas = 0
    for pregunta in preguntas_sin_respuestas:
        if generadas >= limite:
            break
        if responder_automaticamente_si_vencio(pregunta) is not None:
            generadas += 1
    return generadas
