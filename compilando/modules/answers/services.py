"""Lógica de negocio y validaciones para las respuestas a preguntas."""

from sqlalchemy import select

from compilando.extensions import db
from compilando.modules.answers.models import Respuesta
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
