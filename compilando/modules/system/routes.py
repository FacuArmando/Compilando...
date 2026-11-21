"""Rutas iniciales disponibles en esta entrega."""

from flask import Blueprint, g, render_template, request
from sqlalchemy import or_, select

from compilando.extensions import db
from compilando.modules.answers.models import EstadoRespuesta, Respuesta
from compilando.modules.categories.models import Categoria
from compilando.modules.questions.models import Pregunta
from compilando.modules.auth.services import edad_usuario_hoy, es_cumpleanos_hoy

bp = Blueprint("system", __name__)

PREGUNTAS_POR_PAGINA = 10


@bp.get("/")
def index():
    """Mostrar el feed de preguntas con búsqueda, filtros y paginación."""

    busqueda = request.args.get("q", "").strip()
    categoria_id = request.args.get("categoria", type=int)
    pagina = max(1, request.args.get("page", 1, type=int) or 1)

    consulta = select(Pregunta)

    # Buscar palabras en el título o en el cuerpo.
    if busqueda:
        termino = f"%{busqueda}%"
        consulta = consulta.where(
            or_(
                Pregunta.titulo.ilike(termino),
                Pregunta.cuerpo_detallado.ilike(termino),
            )
        )

    # Filtrar por categoría seleccionada.
    if categoria_id is not None:
        consulta = consulta.where(Pregunta.categoria_id == categoria_id)

        if busqueda:
            # Al buscar, mostrar primero las preguntas con respuestas aceptadas.
            consulta = consulta.order_by(
                Pregunta.respuestas.any(Respuesta.estado == EstadoRespuesta.ACEPTADA.value).desc(),
                Pregunta.fecha.desc(),
                Pregunta.id.desc(),
            )
    else:
        # Sin búsqueda, mostrar primero las preguntas más recientes.
        consulta = consulta.order_by(
            Pregunta.fecha.desc(),
            Pregunta.id.desc(),
        )

    paginacion = db.paginate(
        consulta,
        page=pagina,
        per_page=PREGUNTAS_POR_PAGINA,
        error_out=False,
    )

    categorias = db.session.scalars(select(Categoria).order_by(Categoria.nombre)).all()

    return render_template(
        "system/index.html",
        preguntas=paginacion.items,
        paginacion=paginacion,
        categorias=categorias,
        busqueda=busqueda,
        categoria_seleccionada=categoria_id,
        es_cumpleanos=es_cumpleanos_hoy(g.usuario_actual) if g.usuario_actual else False,
        edad_cumpleanos=edad_usuario_hoy(g.usuario_actual) if g.usuario_actual else None,
    )


@bp.get("/health")
def health():
    """Indicar que el proceso web responde; no evalúa servicios externos."""
    return {"status": "ok", "application": "compilando"}
