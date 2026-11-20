"""Rutas HTTP para publicar y modificar respuestas a preguntas."""

from flask import Blueprint, abort, flash, g, redirect, request, url_for
from sqlalchemy import select

from compilando.extensions import db
from compilando.modules.answers.models import Respuesta
from compilando.modules.answers.services import (
    aceptar_respuesta,
    editar_respuesta,
    publicar_respuesta,
)
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


@bp.post("/answers/<int:respuesta_id>/edit")
def edit_answer(respuesta_id: int):
    """Permite al autor modificar el contenido de su propia respuesta."""
    if g.usuario_actual is None:
        abort(401)

    respuesta = db.session.scalar(select(Respuesta).where(Respuesta.id == respuesta_id))
    if respuesta is None:
        abort(404)

    if respuesta.es_ia or respuesta.usuario_id != g.usuario_actual.id:
        abort(403)

    nuevo_cuerpo = request.form.get("cuerpo", "")

    try:
        editar_respuesta(
            respuesta_id=respuesta_id,
            nuevo_cuerpo=nuevo_cuerpo,
            usuario=g.usuario_actual,
        )
        flash("Tu respuesta fue actualizada correctamente.", "success")
    except ValueError as error:
        flash(str(error), "error")

    return redirect(url_for("questions.view_question", pregunta_id=respuesta.pregunta_id))


@bp.post("/answers/<int:respuesta_id>/accept")
def accept_answer(respuesta_id: int):
    """Permite al autor de una pregunta aceptar una respuesta."""

    if g.usuario_actual is None:
        abort(401)

    respuesta = db.session.scalar(select(Respuesta).where(Respuesta.id == respuesta_id))

    if respuesta is None:
        abort(404)

    try:
        aceptar_respuesta(
            respuesta_id=respuesta_id,
            usuario=g.usuario_actual,
        )
        flash("La respuesta fue aceptada correctamente.", "success")

    except PermissionError:
        abort(403)

    return redirect(
        url_for(
            "questions.view_question",
            pregunta_id=respuesta.pregunta_id,
        )
    )
