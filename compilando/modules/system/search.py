"""Preparar coincidencias por término sin modificar el texto escrito por el usuario."""

from sqlalchemy import case, false, func, literal, or_

from compilando.extensions import db
from compilando.modules.questions.models import Pregunta
from compilando.modules.tags.models import Tag
from compilando.search_text import normalizar_busqueda

PESO_TITULO = 8
PESO_ETIQUETA = 4
PESO_CUERPO = 1
PALABRAS_FUNCIONALES = frozenset({"de", "del", "el", "la", "los", "las", "en"})
FRASE_POO = ("programacion", "orientada", "a", "objetos")
ALTERNATIVAS_POO = ("poo", "programación orientada a objetos", "programacion orientada a objetos")


def terminos_busqueda(texto: str, normalizar: bool = True):
    """Interpretar artículos y la equivalencia POO sin cambiar la consulta visible."""
    palabras = texto.split()
    claves = [normalizar_busqueda(palabra) for palabra in palabras]
    vistos = set()
    terminos = []
    indice = 0
    while indice < len(palabras):
        if tuple(claves[indice : indice + 4]) == FRASE_POO:
            termino = "poo"
            indice += 4
        else:
            termino = claves[indice] if normalizar else palabras[indice]
            indice += 1
        clave = normalizar_busqueda(termino)
        if not clave or clave in PALABRAS_FUNCIONALES or clave in vistos:
            continue
        vistos.add(clave)
        terminos.append(termino)
    return terminos


def criterios_busqueda(texto: str):
    """Exigir cada término y puntuar su mejor coincidencia, sin multiplicar por etiquetas."""
    filtros = []
    relevancia = literal(0)
    if db.engine.dialect.name == "postgresql":
        titulo_campo, cuerpo_campo, tag_campo = (
            Pregunta.titulo_busqueda,
            Pregunta.cuerpo_busqueda,
            Tag.nombre_busqueda,
        )
    else:
        titulo_campo, cuerpo_campo, tag_campo = (
            func.normalizar_busqueda(campo)
            for campo in (Pregunta.titulo, Pregunta.cuerpo_detallado, Tag.nombre)
        )
    for termino in terminos_busqueda(texto):
        alternativas = ALTERNATIVAS_POO if termino.casefold() == "poo" else (termino,)
        patrones = {normalizar_busqueda(valor) for valor in alternativas}
        patrones = [
            "%" + valor.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            for valor in sorted(patrones)
        ]
        titulo = or_(*(titulo_campo.ilike(patron, escape="\\") for patron in patrones))
        etiqueta = Pregunta.tags.any(
            or_(*(tag_campo.ilike(patron, escape="\\") for patron in patrones))
        )
        cuerpo = or_(*(cuerpo_campo.ilike(patron, escape="\\") for patron in patrones))
        filtros.append(or_(titulo, etiqueta, cuerpo))
        relevancia += case(
            (titulo, PESO_TITULO),
            (etiqueta, PESO_ETIQUETA),
            (cuerpo, PESO_CUERPO),
            else_=0,
        )
    return filtros or [false()], relevancia
