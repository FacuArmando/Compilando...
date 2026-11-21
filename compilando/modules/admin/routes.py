from flask import Blueprint, flash, redirect, render_template, request, url_for

from compilando.extensions import db
from compilando.modules.auth.sessions import requiere_admin
from compilando.modules.categories.models import Categoria
from compilando.modules.questions.services import normalizar_nombre
from compilando.modules.tags.models import Tag

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("/")
@requiere_admin
def index():
    categorias = db.session.scalars(
        db.select(Categoria).order_by(Categoria.nombre)
    ).all()

    tags = db.session.scalars(
        db.select(Tag).order_by(Tag.nombre)
    ).all()

    return render_template(
        "admin/index.html",
        categorias=categorias,
        tags=tags,
    )


@bp.route("/categorias/<int:categoria_id>/editar", methods=["GET", "POST"])
@requiere_admin
def editar_categoria(categoria_id):
    categoria = db.session.get(Categoria, categoria_id)

    if categoria is None:
        flash("La categoría que intentás editar no existe.", "error")
        return redirect(url_for("admin.index"))

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        descripcion = request.form.get("descripcion", "").strip()

        if not nombre:
            flash("El nombre de la categoría es obligatorio.", "error")
            return render_template(
                "admin/editar_categoria.html",
                categoria=categoria,
            )

        if len(nombre) > 100:
            flash("El nombre no puede superar los 100 caracteres.", "error")
            return render_template(
                "admin/editar_categoria.html",
                categoria=categoria,
            )

        categorias_existentes = db.session.scalars(
            db.select(Categoria).where(Categoria.id != categoria.id)
        ).all()

        nombre_normalizado = normalizar_nombre(nombre)

        for existente in categorias_existentes:
            if normalizar_nombre(existente.nombre) == nombre_normalizado:
                flash("Ya existe una categoría con ese nombre.", "error")
                return render_template(
                    "admin/editar_categoria.html",
                    categoria=categoria,
                )

        categoria.nombre = nombre
        categoria.descripcion = descripcion

        db.session.commit()

        flash("La categoría se actualizó correctamente.", "success")
        return redirect(url_for("admin.index"))

    return render_template(
        "admin/editar_categoria.html",
        categoria=categoria,
    )

@bp.route("/etiquetas/<int:tag_id>/editar", methods=["GET", "POST"])
@requiere_admin
def editar_tag(tag_id):
    tag = db.session.get(Tag, tag_id)

    if tag is None:
        flash("La etiqueta que intentás editar no existe.", "error")
        return redirect(url_for("admin.index"))

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()

        if not nombre:
            flash("El nombre de la etiqueta es obligatorio.", "error")
            return render_template(
                "admin/editar_tag.html",
                tag=tag,
            )

        if len(nombre) > 50:
            flash("El nombre no puede superar los 50 caracteres.", "error")
            return render_template(
                "admin/editar_tag.html",
                tag=tag,
            )

        tags_existentes = db.session.scalars(
            db.select(Tag).where(Tag.id != tag.id)
        ).all()

        nombre_normalizado = normalizar_nombre(nombre)

        for existente in tags_existentes:
            if normalizar_nombre(existente.nombre) == nombre_normalizado:
                flash("Ya existe una etiqueta con ese nombre.", "error")
                return render_template(
                    "admin/editar_tag.html",
                    tag=tag,
                )

        tag.nombre = nombre

        db.session.commit()

        flash("La etiqueta se actualizó correctamente.", "success")
        return redirect(url_for("admin.index"))

    return render_template(
        "admin/editar_tag.html",
        tag=tag,
    )

@bp.post("/etiquetas/<int:tag_id>/eliminar")
@requiere_admin
def eliminar_tag(tag_id):
    tag = db.session.get(Tag, tag_id)

    if tag is None:
        flash("La etiqueta que intentás eliminar no existe.", "error")
        return redirect(url_for("admin.index"))

    nombre_tag = tag.nombre

    # Quitamos las asociaciones con las preguntas.
    tag.preguntas.clear()

    db.session.delete(tag)
    db.session.commit()

    flash(
        f"La etiqueta '{nombre_tag}' se eliminó correctamente.",
        "success",
    )

    return redirect(url_for("admin.index"))