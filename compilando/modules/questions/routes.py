from io import BytesIO

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from sqlalchemy import func, select

from compilando.extensions import db
from compilando.modules.answers.feedback import resumen_evaluaciones
from compilando.modules.answers.models import EstadoRespuesta, Respuesta
from compilando.modules.categories.models import Categoria
from compilando.modules.questions.attachments import (
    AdjuntosInvalidos,
    contenido_adjunto,
    leer_adjunto,
    opciones_adjuntos,
)
from compilando.modules.questions.models import AdjuntoPregunta, Pregunta
from compilando.modules.questions.services import publicar_pregunta
from compilando.modules.saved.services import ids_guardadas
from compilando.modules.tags.models import Tag

bp = Blueprint("questions", __name__)


@bp.route("/questions/publish", methods=["GET", "POST"])
def publish_question():

    if g.usuario_actual is None:
        abort(401)

    # Valores iniciales para mostrar el formulario vacío
    titulo = ""
    cuerpo = ""
    categoria_nombre = ""
    tags_texto = ""
    error_titulo = False
    error_cuerpo = False
    error_categoria = False
    error_adjuntos = ""
    archivos = []
    estado = 200

    if request.method == "POST":
        titulo = request.form.get("titulo", "")
        cuerpo = request.form.get("cuerpo", "")
        categoria_nombre = request.form.get("categoria", "")
        tags_texto = request.form.get("tags", "")
        nombres_tags = tags_texto.split(",")
        archivos = request.files.getlist("archivos")

        try:
            if any(campo != "archivos" for campo in request.files):
                raise AdjuntosInvalidos("Agregá los archivos desde el selector de adjuntos.")
            nueva_pregunta = publicar_pregunta(
                titulo=titulo,
                cuerpo=cuerpo,
                categoria_nombre=categoria_nombre,
                nombres_tags=nombres_tags,
                usuario=g.usuario_actual,
                archivos=archivos,
            )

            return redirect(url_for("questions.view_question", pregunta_id=nueva_pregunta.id))

        except AdjuntosInvalidos as error:
            error_adjuntos = str(error)
            estado = 400
        except OSError:
            current_app.logger.exception("No se pudieron guardar los adjuntos de la pregunta.")
            error_adjuntos = "No pudimos guardar los archivos. Volvé a intentarlo en unos minutos."
            estado = 503
        except ValueError as error:
            mensaje = str(error).lower()

            error_titulo = "título" in mensaje
            error_cuerpo = "cuerpo" in mensaje
            error_categoria = "categoría" in mensaje

            if not error_titulo and not error_cuerpo and not error_categoria:
                flash(str(error), "error")

    # Estas consultas se ejecutan tanto para GET como para POST
    categorias = db.session.scalars(select(Categoria).order_by(Categoria.nombre)).all()

    tags = db.session.scalars(select(Tag).order_by(Tag.nombre)).all()

    return render_template(
        "questions/publish_question.html",
        categorias=categorias,
        tags=tags,
        titulo=titulo,
        cuerpo=cuerpo,
        categoria_nombre=categoria_nombre,
        tags_texto=tags_texto,
        error_titulo=error_titulo,
        error_cuerpo=error_cuerpo,
        error_categoria=error_categoria,
        error_adjuntos=error_adjuntos,
        reseleccionar_adjuntos=any(archivo.filename for archivo in archivos),
        limites_adjuntos=opciones_adjuntos(),
    ), estado


@bp.errorhandler(413)
def carga_demasiado_grande(error):
    return render_template(
        "questions/upload_too_large.html", limites_adjuntos=opciones_adjuntos()
    ), 413


def _obtener_adjunto(pregunta_id: int, adjunto_id: str) -> AdjuntoPregunta:
    adjunto = db.session.scalar(
        select(AdjuntoPregunta).where(
            AdjuntoPregunta.id == adjunto_id, AdjuntoPregunta.pregunta_id == pregunta_id
        )
    )
    if adjunto is None:
        abort(404)
    return adjunto


@bp.get("/questions/<int:pregunta_id>/attachments/<adjunto_id>")
def view_attachment(pregunta_id: int, adjunto_id: str):
    adjunto = _obtener_adjunto(pregunta_id, adjunto_id)
    return render_template(
        "questions/view_attachment.html", adjunto=adjunto, codigo=leer_adjunto(adjunto)
    )


@bp.get("/questions/<int:pregunta_id>/attachments/<adjunto_id>/download")
def download_attachment(pregunta_id: int, adjunto_id: str):
    adjunto = _obtener_adjunto(pregunta_id, adjunto_id)
    return send_file(
        BytesIO(contenido_adjunto(adjunto)),
        as_attachment=True,
        download_name=adjunto.nombre_original,
        mimetype="application/octet-stream",
    )


@bp.get("/questions/publish/success")
def publish_success():
    return render_template("questions/publish_success.html")


@bp.get("/questions/<int:pregunta_id>")
def view_question(pregunta_id: int):
    """Muestra una pregunta y sus respuestas ordenadas."""

    pregunta = db.session.scalar(select(Pregunta).where(Pregunta.id == pregunta_id))

    if pregunta is None:
        abort(404)

    # Mostrar primero la respuesta aceptada.
    respuestas_ordenadas = sorted(
        pregunta.respuestas,
        key=lambda respuesta: respuesta.estado != EstadoRespuesta.ACEPTADA.value,
    )

    preguntas_historial = db.session.execute(
        select(Pregunta.id, Pregunta.titulo, func.count(Respuesta.id).label("cantidad_respuestas"))
        .outerjoin(Respuesta, Respuesta.pregunta_id == Pregunta.id)
        .where(Pregunta.id != pregunta.id)
        .group_by(Pregunta.id, Pregunta.titulo)
        .order_by(Pregunta.id.desc())
        .limit(5)
    ).all()

    return render_template(
        "questions/view_question.html",
        pregunta=pregunta,
        preguntas_historial=preguntas_historial,
        respuestas=respuestas_ordenadas,
        evaluaciones=resumen_evaluaciones(respuestas_ordenadas, g.usuario_actual),
        guardadas_ids=ids_guardadas(
            [pregunta.id], g.usuario_actual.id if g.usuario_actual else None
        ),
    )
