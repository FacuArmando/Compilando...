"""Una sugerencia conservadora, solo si lleva a resultados reales."""

from sqlalchemy import select

from compilando.extensions import db
from compilando.modules.questions.models import Pregunta
from compilando.modules.system.search import PALABRAS_FUNCIONALES, criterios_busqueda
from compilando.modules.tags.models import Tag
from compilando.search_text import normalizar_busqueda


def _un_error(original: str, candidato: str) -> bool:
    if original.count("ñ") != candidato.count("ñ"):
        return False
    if len(original) == len(candidato):
        diferencias = [
            i for i, (a, b) in enumerate(zip(original, candidato, strict=True)) if a != b
        ]
        if len(diferencias) == 1:
            return True
        return (
            len(diferencias) == 2
            and diferencias[1] == diferencias[0] + 1
            and original[diferencias[0]] == candidato[diferencias[1]]
            and original[diferencias[1]] == candidato[diferencias[0]]
        )
    corta, larga = sorted((original, candidato), key=len)
    return len(larga) == len(corta) + 1 and any(
        corta == larga[:i] + larga[i + 1 :] for i in range(len(larga))
    )


def sugerir_busqueda(texto: str, categorias: list[str], categoria_id: int | None = None):
    """No reemplazar términos automáticamente, ni sugerir coincidencias ambiguas."""
    palabras = texto.split()
    if len(texto) > 200 or len(palabras) > 12:
        return None
    nombres = list(db.session.scalars(select(Tag.nombre).order_by(Tag.nombre).limit(300)))
    vocabulario = {}
    for nombre in [*nombres, *categorias]:
        for palabra in nombre.split():
            clave = normalizar_busqueda(palabra)
            if 4 <= len(clave) <= 40 and clave.isalpha() and clave not in PALABRAS_FUNCIONALES:
                vocabulario.setdefault(clave, palabra)
    for indice, palabra in enumerate(palabras):
        clave = normalizar_busqueda(palabra)
        if clave in vocabulario or clave in PALABRAS_FUNCIONALES or clave == "poo":
            continue
        if not 4 <= len(clave) <= 40 or not clave.isalpha():
            continue
        candidatos = [valor for valor in vocabulario if _un_error(clave, valor)]
        if len(candidatos) != 1:
            return None
        propuesta = " ".join(
            [*palabras[:indice], vocabulario[candidatos[0]], *palabras[indice + 1 :]]
        )
        filtros, _ = criterios_busqueda(propuesta)
        consulta = select(Pregunta.id).where(*filtros)
        if categoria_id is not None:
            consulta = consulta.where(Pregunta.categoria_id == categoria_id)
        return propuesta if db.session.scalar(consulta.limit(1)) is not None else None
    return None
