"""Rutas iniciales disponibles en esta entrega."""

from flask import Blueprint, redirect, render_template, request, url_for
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload, selectinload

from compilando.extensions import db
from compilando.modules.answers.models import EstadoRespuesta, Respuesta
from compilando.modules.auth.models import Usuario
from compilando.modules.categories.models import Categoria
from compilando.modules.questions.models import Pregunta
from compilando.modules.tags.models import Tag

bp = Blueprint("system", __name__)

PREGUNTAS_POR_PAGINA = 20
# SQLite acepta offsets de hasta 64 bits; una URL arbitraria no debe desbordarlos.
MAXIMA_PAGINA = (2**63 - 1) // PREGUNTAS_POR_PAGINA


@bp.get("/")
def index():
    """Mostrar el feed de preguntas con búsqueda, filtros y paginación."""

    busqueda = request.args.get("q", "").strip()
    categoria_id = request.args.get("categoria", type=int)
    pagina = request.args.get("page", type=int) if "page" in request.args else 1

    def primera_pagina():
        return redirect(
            url_for(
                "system.index",
                q=busqueda or None,
                categoria=categoria_id,
                _anchor="preguntas",
            )
        )

    if pagina is None or not 1 <= pagina <= MAXIMA_PAGINA:
        return primera_pagina()

    consulta = select(Pregunta).options(
        joinedload(Pregunta.usuario).load_only(Usuario.username, Usuario.avatar_filename),
        joinedload(Pregunta.categoria).load_only(Categoria.nombre),
        selectinload(Pregunta.tags).load_only(Tag.nombre),
    )

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
            )

    # La fecha y el ID dan un orden estable, también al filtrar solo por categoría.
    consulta = consulta.order_by(Pregunta.fecha.desc(), Pregunta.id.desc())

    paginacion = db.paginate(
        consulta,
        page=pagina,
        per_page=PREGUNTAS_POR_PAGINA,
        max_per_page=PREGUNTAS_POR_PAGINA,
        error_out=False,
    )

    if pagina > 1 and not paginacion.items:
        return primera_pagina()

    # Contar solo las respuestas de esta página, sin cargar sus cuerpos en memoria.
    ids = [pregunta.id for pregunta in paginacion.items]
    cantidad_respuestas = (
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
    categorias = db.session.scalars(select(Categoria).order_by(Categoria.nombre)).all()

    return render_template(
        "system/index.html",
        preguntas=paginacion.items,
        paginacion=paginacion,
        cantidad_respuestas=cantidad_respuestas,
        priorizar_aceptadas=bool(busqueda and categoria_id is not None),
        categorias=categorias,
        busqueda=busqueda,
        categoria_seleccionada=categoria_id,
    )


@bp.get("/health")
def health():
    """Indicar que el proceso web responde; no evalúa servicios externos."""
    return {"status": "ok", "application": "compilando"}
