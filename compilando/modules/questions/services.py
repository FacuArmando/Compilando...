import unicodedata

from sqlalchemy import select

from compilando.extensions import db
from compilando.modules.auth.models import Usuario
from compilando.modules.categories.models import Categoria
from compilando.modules.questions.models import Pregunta
from compilando.modules.tags.models import Tag


def normalizar_nombre(nombre: str) -> str:
    nombre = nombre.strip().casefold()

    nombre = unicodedata.normalize("NFD", nombre)

    return "".join(caracter for caracter in nombre if unicodedata.category(caracter) != "Mn")


def validar_titulo(titulo: str) -> bool:
    return 10 <= len(titulo.strip()) <= 150


def validar_cuerpo(cuerpo: str) -> bool:
    return 3 <= len(cuerpo.strip()) <= 5000


def obtener_o_crear_categoria(nombre: str) -> Categoria:
    nombre = nombre.strip()

    categorias_existentes = db.session.scalars(select(Categoria)).all()

    for categoria in categorias_existentes:
        if normalizar_nombre(categoria.nombre) == normalizar_nombre(nombre):
            return categoria

    categoria = Categoria(nombre=nombre, descripcion="")

    db.session.add(categoria)

    return categoria


def obtener_o_crear_tag(nombre: str) -> Tag:
    nombre = nombre.strip()

    tags_existentes = db.session.scalars(select(Tag)).all()

    for tag in tags_existentes:
        if normalizar_nombre(tag.nombre) == normalizar_nombre(nombre):
            return tag

    tag = Tag(nombre=nombre)
    db.session.add(tag)

    return tag


"""Función encargada de publicar las preguntas a la plataforma"""


def publicar_pregunta(
    titulo: str, cuerpo: str, categoria_nombre: str, nombres_tags: list[str], usuario: Usuario
) -> Pregunta:

    if not validar_titulo(titulo):
        raise ValueError("El título debe tener entre 10 y 150 caracteres.")

    if not validar_cuerpo(cuerpo):
        raise ValueError("El cuerpo debe tener entre 3 y 5000 caracteres.")

    if not categoria_nombre.strip():
        raise ValueError("La categoría es obligatoria.")

    try:
        categoria = obtener_o_crear_categoria(categoria_nombre)

        tags = []
        nombres_procesados = set()

        for nombre in nombres_tags:
            nombre = nombre.strip()

            if nombre and nombre.lower() not in nombres_procesados:
                tag = obtener_o_crear_tag(nombre)
                tags.append(tag)
                nombres_procesados.add(nombre.lower())

        pregunta = Pregunta(
            titulo=titulo.strip(),
            cuerpo_detallado=cuerpo.strip(),
            usuario=usuario,
            categoria=categoria,
            tags=tags,
        )

        db.session.add(pregunta)
        db.session.commit()

        return pregunta

    except Exception:
        db.session.rollback()
        raise
