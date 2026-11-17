"""Lógica de negocio y validaciones para las respuestas a preguntas."""

from datetime import datetime

from sqlalchemy import select

from compilando.extensions import db
from compilando.modules.answers.models import EstadoRespuesta, Respuesta
from compilando.modules.auth.models import Usuario
from compilando.modules.questions.models import Pregunta


def validar_cuerpo(cuerpo: str) -> bool:
    """Verifica que el contenido de la respuesta tenga entre 3 y 5000 caracteres."""
    return 3 <= len(cuerpo.strip()) <= 5000


def publicar_respuesta(pregunta_id: int, cuerpo: str, usuario: Usuario) -> Respuesta:
    """Valida y guarda una nueva respuesta asociada a una pregunta y a su autor."""
    if not validar_cuerpo(cuerpo):
        raise ValueError("El cuerpo de la respuesta debe tener entre 3 y 5000 caracteres.")

    pregunta = db.session.scalar(select(Pregunta).where(Pregunta.id == pregunta_id))
    if pregunta is None:
        raise ValueError("La pregunta que intentás responder no existe.")

    try:
        respuesta = Respuesta(
            cuerpo=cuerpo.strip(),
            pregunta=pregunta,
            usuario=usuario,
        )
        db.session.add(respuesta)
        db.session.commit()
        return respuesta
    except Exception:
        db.session.rollback()
        raise


def editar_respuesta(respuesta_id: int, nuevo_cuerpo: str, usuario: Usuario) -> Respuesta:
    """Actualiza el contenido de una respuesta existente si pertenece al usuario."""
    if not validar_cuerpo(nuevo_cuerpo):
        raise ValueError("El cuerpo de la respuesta debe tener entre 3 y 5000 caracteres.")

    respuesta = db.session.scalar(select(Respuesta).where(Respuesta.id == respuesta_id))
    if respuesta is None:
        raise ValueError("La respuesta que intentás modificar no existe.")

    if respuesta.usuario_id != usuario.id:
        raise PermissionError("Solo el autor de la respuesta puede modificarla.")

    try:
        respuesta.cuerpo = nuevo_cuerpo.strip()
        respuesta.fecha_edicion = datetime.now()
        db.session.commit()
        return respuesta
    except Exception:
        db.session.rollback()
        raise


def aceptar_respuesta(respuesta_id: int, usuario: Usuario) -> Respuesta:
    """Permite al autor de una pregunta aceptar una de sus respuestas."""

    respuesta = db.session.scalar(select(Respuesta).where(Respuesta.id == respuesta_id))

    if respuesta is None:
        raise ValueError("La respuesta que intentás aceptar no existe.")

    if respuesta.pregunta.usuario_id != usuario.id:
        raise PermissionError("Solo el autor de la pregunta puede aceptar una respuesta.")

    try:
        respuestas_aceptadas = db.session.scalars(
            select(Respuesta).where(
                Respuesta.pregunta_id == respuesta.pregunta_id,
                Respuesta.estado == EstadoRespuesta.ACEPTADA.value,
            )
        ).all()

        for respuesta_anterior in respuestas_aceptadas:
            respuesta_anterior.estado = EstadoRespuesta.NO_ACEPTADA.value

        respuesta.estado = EstadoRespuesta.ACEPTADA.value

        db.session.commit()
        return respuesta

    except Exception:
        db.session.rollback()
        raise
