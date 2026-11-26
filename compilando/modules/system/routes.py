"""Rutas iniciales disponibles en esta entrega."""

from flask import Blueprint, g, jsonify, redirect, render_template, request, url_for
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from compilando.extensions import db
from compilando.modules.answers.highlights import preguntas_utiles_semana
from compilando.modules.answers.models import EstadoRespuesta, Respuesta
from compilando.modules.auth.models import Usuario
from compilando.modules.categories.models import Categoria
from compilando.modules.questions.models import Pregunta
from compilando.modules.saved.services import ids_guardadas
from compilando.modules.system.autocomplete import sugerencias_preguntas
from compilando.modules.system.search import criterios_busqueda, terminos_busqueda
from compilando.modules.system.suggestions import sugerir_busqueda
from compilando.modules.tags.models import Tag

bp = Blueprint("system", __name__)

PREGUNTAS_POR_PAGINA = 20
# SQLite acepta offsets de hasta 64 bits; una URL arbitraria no debe desbordarlos.
MAXIMA_PAGINA = (2**63 - 1) // PREGUNTAS_POR_PAGINA


@bp.get("/search/suggestions")
def search_suggestions():
    """Ofrecer hasta cinco destinos públicos sin almacenar búsquedas del visitante."""
    categoria = request.args.get("categoria", "")
    categoria_id = request.args.get("categoria", type=int)
    # Un filtro inválido no debe ampliar silenciosamente la búsqueda.
    if categoria and (categoria_id is None or not 0 < categoria_id < 2**63):
        response = jsonify(preguntas=[])
        response.status_code = 400
    else:
        preguntas = sugerencias_preguntas(request.args.get("q", ""), categoria_id)
        response = jsonify(
            preguntas=[
                {
                    "id": pregunta.id,
                    "titulo": pregunta.titulo,
                    "categoria": pregunta.categoria,
                    "url": url_for("questions.view_question", pregunta_id=pregunta.id),
                }
                for pregunta in preguntas
            ]
        )
    response.headers["Cache-Control"] = "no-store"
    return response


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

    # Cada término debe aparecer; priorizar título, etiquetas y luego cuerpo.
    if busqueda:
        filtros, relevancia = criterios_busqueda(busqueda)
        consulta = consulta.where(*filtros).order_by(
            relevancia.desc(),
            Pregunta.respuestas.any(Respuesta.estado == EstadoRespuesta.ACEPTADA.value).desc(),
        )

    # Filtrar por categoría seleccionada.
    if categoria_id is not None:
        consulta = consulta.where(Pregunta.categoria_id == categoria_id)

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
    sugerencia = (
        sugerir_busqueda(busqueda, [categoria.nombre for categoria in categorias], categoria_id)
        if busqueda and paginacion.total == 0 and terminos_busqueda(busqueda)
        else None
    )

    return render_template(
        "system/index.html",
        preguntas=paginacion.items,
        paginacion=paginacion,
        cantidad_respuestas=cantidad_respuestas,
        guardadas_ids=ids_guardadas(ids, g.usuario_actual.id if g.usuario_actual else None),
        categorias=categorias,
        busqueda=busqueda,
        sugerencia_busqueda=sugerencia,
        consulta_sin_terminos=bool(busqueda and not terminos_busqueda(busqueda)),
        categoria_seleccionada=categoria_id,
        mostrar_destacados=not busqueda and categoria_id is None and pagina == 1,
        destacados=(
            preguntas_utiles_semana()
            if not busqueda and categoria_id is None and pagina == 1
            else []
        ),
    )


@bp.get("/health")
def health():
    """Indicar que el proceso web responde; no evalúa servicios externos."""
    return {"status": "ok", "application": "compilando"}
