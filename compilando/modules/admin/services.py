import hmac

from flask import current_app
from sqlalchemy import select

from compilando.extensions import db
from compilando.modules.categories.models import Categoria
from compilando.modules.questions.services import normalizar_nombre
from compilando.modules.tags.models import Tag


def activar_administrador(usuario, codigo: str) -> bool:
    """Activar el rol de administrador si el código proporcionado es válido."""

    if usuario.es_admin:
        return False

    codigo_configurado = current_app.config.get("ADMIN_ACTIVATION_CODE", "")

    if not codigo_configurado:
        raise RuntimeError("El código de activación no está configurado.")

    if not isinstance(codigo, str) or not codigo:
        raise ValueError("Ingresá un código de activación.")

    if not hmac.compare_digest(codigo, codigo_configurado):
        raise ValueError("El código de activación es incorrecto.")

    usuario.es_admin = True

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return True


def crear_categoria(nombre: str, descripcion: str) -> Categoria:
    """Crear una categoría nueva."""

    nombre = nombre.strip()
    descripcion = descripcion.strip()

    if not nombre:
        raise ValueError("Ingresá un nombre para la categoría.")

    if len(nombre) > 100:
        raise ValueError("El nombre no puede superar los 100 caracteres.")

    if not descripcion:
        raise ValueError("Ingresá una descripción para la categoría.")

    categorias = db.session.scalars(select(Categoria)).all()

    for categoria in categorias:
        if normalizar_nombre(categoria.nombre) == normalizar_nombre(nombre):
            raise ValueError("Ya existe una categoría con ese nombre.")

    categoria = Categoria(
        nombre=nombre,
        descripcion=descripcion,
    )

    db.session.add(categoria)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return categoria


def editar_categoria(categoria_id: int, nombre: str, descripcion: str) -> Categoria:
    """Actualizar el nombre y la descripción de una categoría."""

    categoria = db.session.get(Categoria, categoria_id)

    if categoria is None:
        raise LookupError("La categoría no existe.")

    nombre = nombre.strip()
    descripcion = descripcion.strip()

    if not nombre:
        raise ValueError("Ingresá un nombre para la categoría.")

    if len(nombre) > 100:
        raise ValueError("El nombre no puede superar los 100 caracteres.")

    if not descripcion:
        raise ValueError("Ingresá una descripción para la categoría.")

    categorias = db.session.scalars(select(Categoria)).all()

    for existente in categorias:
        if existente.id != categoria.id:
            if normalizar_nombre(existente.nombre) == normalizar_nombre(nombre):
                raise ValueError("Ya existe una categoría con ese nombre.")

    categoria.nombre = nombre
    categoria.descripcion = descripcion

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return categoria


def eliminar_tag(tag_id: int) -> None:
    """Eliminar una etiqueta y sus asociaciones con preguntas."""
    tag = db.session.get(Tag, tag_id)

    if tag is None:
        raise LookupError("La etiqueta no existe.")

    # Desvincular la etiqueta de todas sus preguntas.
    tag.preguntas.clear()

    db.session.delete(tag)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def crear_tag(nombre: str) -> Tag:
    """Crear una etiqueta nueva."""
    nombre = nombre.strip()

    if not nombre:
        raise ValueError("Ingresá un nombre para la etiqueta.")

    if len(nombre) > 50:
        raise ValueError("El nombre no puede superar los 50 caracteres.")

    etiquetas = db.session.scalars(select(Tag)).all()

    for etiqueta in etiquetas:
        if normalizar_nombre(etiqueta.nombre) == normalizar_nombre(nombre):
            raise ValueError("Ya existe una etiqueta con ese nombre.")

    tag = Tag(nombre=nombre)

    db.session.add(tag)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return tag


def editar_tag(tag_id: int, nombre: str) -> Tag:
    """Editar el nombre de una etiqueta existente."""
    tag = db.session.get(Tag, tag_id)

    if tag is None:
        raise LookupError("La etiqueta no existe.")

    nombre = nombre.strip()

    if not nombre:
        raise ValueError("Ingresá un nombre para la etiqueta.")

    if len(nombre) > 50:
        raise ValueError("El nombre no puede superar los 50 caracteres.")

    etiquetas = db.session.scalars(select(Tag)).all()

    for etiqueta in etiquetas:
        if etiqueta.id != tag.id and normalizar_nombre(etiqueta.nombre) == normalizar_nombre(
            nombre
        ):
            raise ValueError("Ya existe una etiqueta con ese nombre.")

    tag.nombre = nombre

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return tag
