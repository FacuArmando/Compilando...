"""Listado privado y formularios para guardar o quitar preguntas."""

from urllib.parse import parse_qs, urlsplit

from flask import Blueprint, abort, flash, g, jsonify, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload

from compilando.extensions import db
from compilando.i18n import tr
from compilando.modules.answers.models import Respuesta
from compilando.modules.auth.models import Usuario
from compilando.modules.categories.models import Categoria
from compilando.modules.questions.models import Pregunta
from compilando.modules.saved.models import PreguntaGuardada
from compilando.modules.saved.services import cambiar_guardado, ids_guardadas
from compilando.modules.tags.models import Tag

bp = Blueprint("saved", __name__)
POR_PAGINA = 20
MAXIMA_PAGINA = (2**63 - 1) // POR_PAGINA


@bp.after_request
def coleccion_privada(response):
    response.headers["Cache-Control"] = "no-store"
    response.vary.add("Cookie")
    return response


@bp.errorhandler(CSRFError)
def csrf_vencido(error):
    if request.accept_mimetypes.best == "application/json":
        return jsonify(error=tr("Tu formulario venció. Recargá la página para guardar.")), 400
    return error.get_response()


@bp.get("/saved")
def index():
    if g.usuario_actual is None:
        return redirect(url_for("auth.login", next=url_for("saved.index")), code=303)
    pagina = request.args.get("page", type=int) if "page" in request.args else 1
    if pagina is None or not 1 <= pagina <= MAXIMA_PAGINA:
        return redirect(url_for("saved.index"))
    consulta = (
        select(Pregunta)
        .join(PreguntaGuardada, PreguntaGuardada.pregunta_id == Pregunta.id)
        .where(PreguntaGuardada.usuario_id == g.usuario_actual.id)
        .options(
            joinedload(Pregunta.usuario).load_only(Usuario.username, Usuario.avatar_filename),
            joinedload(Pregunta.categoria).load_only(Categoria.nombre),
            selectinload(Pregunta.tags).load_only(Tag.nombre),
        )
        .order_by(PreguntaGuardada.fecha.desc(), Pregunta.id.desc())
    )
    paginacion = db.paginate(consulta, page=pagina, per_page=POR_PAGINA, error_out=False)
    if pagina > 1 and not paginacion.items:
        return redirect(url_for("saved.index", page=max(1, paginacion.pages), _anchor="preguntas"))
    ids = [pregunta.id for pregunta in paginacion.items]
    cantidades = (
        dict(
            db.session.execute(
                select(Respuesta.pregunta_id, func.count(Respuesta.id))
                .where(Respuesta.pregunta_id.in_(ids))
                .group_by(Respuesta.pregunta_id)
            ).all()
        )
        if ids
        else {}
    )
    return render_template(
        "saved/index.html",
        preguntas=paginacion.items,
        paginacion=paginacion,
        cantidad_respuestas=cantidades,
        guardadas_ids=set(ids),
        vista_guardadas=True,
        busqueda="",
        categoria_seleccionada=None,
        categorias=db.session.scalars(select(Categoria).order_by(Categoria.nombre)).all(),
    )


def _regreso(pregunta_id):
    defecto = url_for("questions.view_question", pregunta_id=pregunta_id)
    valor = request.form.get("volver", "")
    if len(valor) > 2048 or "\\" in valor or any(c.isspace() for c in valor):
        return defecto
    try:
        ruta = urlsplit(valor)
        if ruta.scheme or ruta.netloc:
            return defecto
        parametros = parse_qs(ruta.query, max_num_fields=10)
        pagina = int(parametros.get("page", ["1"])[0])
        if not 1 <= pagina <= MAXIMA_PAGINA:
            return defecto
        if ruta.path == url_for("saved.index"):
            return url_for("saved.index", page=pagina, _anchor="preguntas")
        if ruta.path == url_for("system.index"):
            categoria = parametros.get("categoria", [None])[0]
            if categoria is not None and not 0 < int(categoria) < 2**63:
                return defecto
            return url_for(
                "system.index",
                page=pagina,
                q=parametros.get("q", [None])[0],
                categoria=categoria,
                _anchor=f"pregunta-{pregunta_id}",
            )
    except ValueError:
        return defecto
    return defecto


@bp.post("/questions/<int:pregunta_id>/saved")
def change(pregunta_id):
    es_json = request.accept_mimetypes.best == "application/json"
    login_url = url_for(
        "auth.login", next=url_for("questions.view_question", pregunta_id=pregunta_id)
    )
    if g.usuario_actual is None:
        if es_json:
            return jsonify(
                error=tr("Iniciá sesión para guardar preguntas."), login_url=login_url
            ), 401
        return redirect(login_url, code=303)
    if not 0 < pregunta_id < 2**63 or db.session.get(Pregunta, pregunta_id) is None:
        if es_json:
            return jsonify(error=tr("Esta pregunta ya no está disponible.")), 404
        abort(404)
    valor = request.form.get("guardada")
    if valor not in {"si", "no"}:
        if es_json:
            return jsonify(error=tr("La opción de guardado no es válida.")), 400
        abort(400)
    try:
        cambiar_guardado(pregunta_id, g.usuario_actual.id, valor == "si")
        guardada = pregunta_id in ids_guardadas([pregunta_id], g.usuario_actual.id)
    except SQLAlchemyError:
        db.session.rollback()
        if es_json:
            return jsonify(error=tr("No pudimos confirmar el guardado. Volvé a intentar.")), 503
        abort(503)
    mensaje = tr("Pregunta guardada." if guardada else "Pregunta quitada de Guardadas.")
    if es_json:
        return jsonify(pregunta_id=pregunta_id, guardada=guardada, mensaje=mensaje)
    flash(mensaje, "success")
    return redirect(_regreso(pregunta_id), code=303)
