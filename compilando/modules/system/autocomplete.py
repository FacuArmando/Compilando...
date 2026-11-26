"""Preguntas públicas para el desplegable del buscador, con una consulta acotada."""

from sqlalchemy import select

from compilando.extensions import db
from compilando.modules.answers.models import EstadoRespuesta, Respuesta
from compilando.modules.categories.models import Categoria
from compilando.modules.questions.models import Pregunta
from compilando.modules.system.search import criterios_busqueda

MINIMO_CARACTERES = 3
MAXIMO_CARACTERES = 200
MAXIMO_PALABRAS = 12
MAXIMO_SUGERENCIAS = 5


def sugerencias_preguntas(texto: str, categoria_id: int | None = None):
    """Usar la relevancia del listado sin cargar cuerpos, autores ni colecciones."""
    texto = texto.strip()
    if not MINIMO_CARACTERES <= len(texto) <= MAXIMO_CARACTERES:
        return []
    if len(texto.split()) > MAXIMO_PALABRAS:
        return []
    filtros, relevancia = criterios_busqueda(texto)
    consulta = (
        select(Pregunta.id, Pregunta.titulo, Categoria.nombre.label("categoria"))
        .join(Categoria, Categoria.id == Pregunta.categoria_id)
        .where(*filtros)
    )
    if categoria_id is not None:
        consulta = consulta.where(Pregunta.categoria_id == categoria_id)
    return db.session.execute(
        consulta.order_by(
            relevancia.desc(),
            Pregunta.respuestas.any(Respuesta.estado == EstadoRespuesta.ACEPTADA.value).desc(),
            Pregunta.fecha.desc(),
            Pregunta.id.desc(),
        ).limit(MAXIMO_SUGERENCIAS)
    ).all()
