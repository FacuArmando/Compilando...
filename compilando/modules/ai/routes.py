"""La generación solo se inicia mediante POST autenticado y protegido por CSRF."""

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_wtf.csrf import CSRFError
from sqlalchemy.exc import SQLAlchemyError

from compilando.extensions import db
from compilando.i18n import tr
from compilando.modules.ai.providers import ErrorIA
from compilando.modules.ai.services import consultar_ia
from compilando.modules.auth.security import DemasiadosIntentos

bp = Blueprint("ai", __name__)


def quiere_json():
    return request.accept_mimetypes.best == "application/json"


def error_consulta(mensaje, status, pregunta_id=None, segundos=None):
    if quiere_json():
        response = jsonify(error=tr(mensaje))
        response.status_code = status
    else:
        flash(mensaje, "error")
        response = redirect(url_for("questions.view_question", pregunta_id=pregunta_id), code=303)
    if segundos:
        response.headers["Retry-After"] = str(segundos)
    return response


@bp.errorhandler(CSRFError)
def csrf_vencido(error):
    if g.get("usuario_actual") is None:
        return pedir_login(request.view_args["pregunta_id"])
    if quiere_json():
        message = tr("El formulario venció. Recargá la página y volvé a intentarlo.")
        return jsonify(error=message), 400
    return error.get_response()


def pedir_login(pregunta_id):
    login_url = url_for(
        "auth.login",
        next=url_for("questions.view_question", pregunta_id=pregunta_id, _anchor="tu-respuesta"),
    )
    if quiere_json():
        return jsonify(error=tr("Iniciá sesión para consultar IA."), login_url=login_url), 401
    return redirect(login_url, code=303)


@bp.post("/questions/<int:pregunta_id>/ai")
def ask(pregunta_id):
    if g.usuario_actual is None:
        return pedir_login(pregunta_id)
    if request.form.get("confirmar_envio") != "si":
        return error_consulta("Confirmá el envío de la pregunta a Gemini.", 400, pregunta_id)
    try:
        respuesta = consultar_ia(
            pregunta_id, g.usuario_actual.id, request.form.get("incluir_adjuntos") == "si"
        )
        if quiere_json():
            respuestas = sorted(respuesta.pregunta.respuestas, key=lambda r: r.estado != "Aceptada")
            return jsonify(
                respuesta_id=respuesta.id,
                cantidad=len(respuestas),
                html=render_template(
                    "answers/_list.html", pregunta=respuesta.pregunta, respuestas=respuestas
                ),
            )
        return redirect(
            url_for(
                "questions.view_question",
                pregunta_id=pregunta_id,
                _anchor=f"respuesta-{respuesta.id}",
            ),
            code=303,
        )
    except DemasiadosIntentos as error:
        return error_consulta(
            "Se alcanzó el límite de consultas de IA. Probá de nuevo más tarde.",
            429,
            pregunta_id,
            error.segundos,
        )
    except ErrorIA as error:
        return error_consulta(str(error), error.status, pregunta_id)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.error(
            "No se pudo guardar la consulta IA; revisar migraciones y conexión."
        )
        return error_consulta(
            "No pudimos guardar la consulta. Avisale al equipo para revisar la base de datos.",
            503,
            pregunta_id,
        )
