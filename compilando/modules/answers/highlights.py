"""Preguntas que ayudaron a lectores distintos durante los últimos siete días."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import distinct, func, select

from compilando.extensions import db
from compilando.modules.answers.models import EvaluacionRespuesta, Respuesta
from compilando.modules.categories.models import Categoria
from compilando.modules.questions.models import Pregunta

DIAS_DESTACADOS = 7
MINIMO_PERSONAS = 3
MAXIMO_DESTACADOS = 3


def preguntas_utiles_semana(ahora: datetime | None = None):
    """Contar una persona una vez por pregunta, aunque valore varias respuestas."""
    ahora = ahora or datetime.now(UTC)
    if ahora.tzinfo is not None:
        ahora = ahora.astimezone(UTC).replace(tzinfo=None)
    lectores = func.count(distinct(EvaluacionRespuesta.usuario_id)).label("personas")
    consulta = (
        select(
            Pregunta.id.label("pregunta_id"),
            Pregunta.titulo,
            Categoria.nombre.label("categoria"),
            lectores,
        )
        .select_from(Pregunta)
        .join(Respuesta, Respuesta.pregunta_id == Pregunta.id)
        .join(EvaluacionRespuesta, EvaluacionRespuesta.respuesta_id == Respuesta.id)
        .join(Categoria, Categoria.id == Pregunta.categoria_id)
        .where(
            EvaluacionRespuesta.util.is_(True),
            EvaluacionRespuesta.fecha_actualizacion >= ahora - timedelta(days=DIAS_DESTACADOS),
            EvaluacionRespuesta.fecha_actualizacion <= ahora,
        )
        .group_by(Pregunta.id, Pregunta.titulo, Categoria.nombre)
        .having(lectores >= MINIMO_PERSONAS)
        .order_by(
            lectores.desc(),
            func.max(EvaluacionRespuesta.fecha_actualizacion).desc(),
            Pregunta.id.desc(),
        )
        .limit(MAXIMO_DESTACADOS)
    )
    return db.session.execute(consulta).all()
