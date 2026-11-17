"""Rutas HTTP para publicar respuestas a preguntas."""

from flask import Blueprint, abort, flash, g, redirect, request, url_for
from sqlalchemy import select

from compilando.extensions import db
from compilando.modules.answers.services import publicar_respuesta
from compilando.modules.questions.models import Pregunta

bp = Blueprint("answers", __name__)


@bp.post("/questions/<int:pregunta_id>/answers")
def publish_answer(pregunta_id: int):
    """Recibe el formulario y publica una nueva respuesta para la pregunta indicada."""
    if g.usuario_actual is None:
        abort(401)

    pregunta = db.session.scalar(select(Pregunta).where(Pregunta.id == pregunta_id))
    if pregunta is None:
        abort(404)

    cuerpo = request.form.get("cuerpo", "")

    try:
        publicar_respuesta(
            pregunta_id=pregunta_id,
            cuerpo=cuerpo,
            usuario=g.usuario_actual,
        )
        flash("Tu respuesta fue publicada correctamente.", "success")
    except ValueError as error:
        flash(str(error), "error")

    return redirect(url_for("questions.view_question", pregunta_id=pregunta_id))