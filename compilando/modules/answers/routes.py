"""Rutas HTTP para publicar y modificar respuestas a preguntas."""

from flask import Blueprint, abort, flash, g, jsonify, redirect, request, url_for
from flask_wtf.csrf import CSRFError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from compilando.extensions import db
from compilando.i18n import tr
from compilando.modules.answers.feedback import evaluar_respuesta, resumen_evaluaciones
from compilando.modules.answers.models import Respuesta
from compilando.modules.answers.services import (
    aceptar_respuesta,
    editar_respuesta,
    publicar_respuesta,
)
from compilando.modules.questions.models import Pregunta

bp = Blueprint("answers", __name__)


@bp.errorhandler(CSRFError)
def csrf_error(error):
    if request.accept_mimetypes.best == "application/json":
        mensaje = "Tu formulario venció. Recargá la pregunta para volver a evaluar."
        return jsonify(error=tr(mensaje)), 400
    return error.get_response()


@bp.post("/answers/<int:respuesta_id>/feedback")
def answer_feedback(respuesta_id: int):
    """Guardar o retirar la evaluación del lector y volver a la misma respuesta."""
    es_json = request.accept_mimetypes.best == "application/json"

    def rechazar(codigo, mensaje):
        if es_json:
            return jsonify(error=tr(mensaje)), codigo
        abort(codigo)

    if g.usuario_actual is None:
        return rechazar(401, "Ingresá de nuevo para dar tu opinión.")
    respuesta = db.session.get(Respuesta, respuesta_id)
    if respuesta is None:
        return rechazar(404, "Esta respuesta ya no está disponible.")

    opciones = {"si": True, "no": False, "retirar": None}
    opcion = request.form.get("utilidad", "")
    if opcion not in opciones:
        return rechazar(400, "La evaluación no es válida. Recargá la pregunta.")
    try:
        evaluar_respuesta(respuesta, g.usuario_actual, opciones[opcion])
        if es_json:
            cantidad, eleccion = resumen_evaluaciones([respuesta], g.usuario_actual)[respuesta.id]
    except PermissionError:
        return rechazar(403, "No podés evaluar tu propia respuesta.")
    except SQLAlchemyError:
        db.session.rollback()
        return rechazar(
            503, "No pudimos confirmar tu evaluación. Recargá la pregunta para comprobarla."
        )
    mensaje = "Retiraste tu evaluación." if opcion == "retirar" else "Gracias por tu opinión."
    if es_json:
        return jsonify(
            respuesta_id=respuesta.id,
            utilidad=eleccion,
            cantidad_utiles=cantidad,
            mensaje=tr(mensaje),
        )
    flash(mensaje, "success")
    return redirect(
        url_for(
            "questions.view_question",
            pregunta_id=respuesta.pregunta_id,
            _anchor=f"respuesta-{respuesta.id}",
        ),
        code=303,
    )


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
