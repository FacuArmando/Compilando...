from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from compilando.modules.auth.security import DemasiadosIntentos, limitar_intentos
from compilando.modules.auth.sessions import requiere_admin, requiere_sesion
from sqlalchemy import select

from compilando.extensions import db
from compilando.modules.admin.services import (
    activar_administrador,
    crear_categoria,
    editar_categoria,
    eliminar_tag,
    crear_tag,
    editar_tag,
)
from compilando.modules.categories.models import Categoria
from compilando.modules.tags.models import Tag

bp = Blueprint("admin", __name__, url_prefix="/admin")

@bp.get("/")
@requiere_admin
def index():
    categorias = db.session.scalars(
        select(Categoria)
        .order_by(Categoria.nombre)
        .limit(5)
    ).all()

    etiquetas = db.session.scalars(
        select(Tag)
        .order_by(Tag.nombre)
        .limit(5)
    ).all()

    total_categorias = db.session.query(Categoria).count()
    total_etiquetas = db.session.query(Tag).count()

    return render_template(
        "admin/index.html",
        categorias=categorias,
        etiquetas=etiquetas,
        total_categorias=total_categorias,
        total_etiquetas=total_etiquetas,
    )


@bp.get("/categories")
@requiere_admin
def categories():
    """Mostrar las categorías disponibles con paginación."""
    busqueda_categoria = request.args.get(
        "busqueda_categoria", ""
    ).strip()

    pagina = max(1, request.args.get("pagina", 1, type=int))
    por_pagina = 10

    consulta = select(Categoria)

    if busqueda_categoria:
        consulta = consulta.where(
            Categoria.nombre.ilike(f"%{busqueda_categoria}%")
        )

    total = db.session.scalar(
        select(db.func.count()).select_from(consulta.subquery())
    )

    total_paginas = max(1, (total + por_pagina - 1) // por_pagina)
    pagina = min(pagina, total_paginas)

    categorias = db.session.scalars(
        consulta
        .order_by(Categoria.nombre)
        .limit(por_pagina)
        .offset((pagina - 1) * por_pagina)
    ).all()

    return render_template(
        "admin/categories.html",
        categorias=categorias,
        busqueda_categoria=busqueda_categoria,
        pagina=pagina,
        total_paginas=total_paginas,
    )


@bp.route("/categories/new", methods=["GET", "POST"])
@requiere_admin
def create_category():
    """Crear una categoría nueva."""

    if request.method == "POST":
        nombre = request.form.get("nombre", "")
        descripcion = request.form.get("descripcion", "")

        try:
            crear_categoria(nombre, descripcion)
        except ValueError as exc:
            flash(str(exc), "error")
        else:
            flash("La categoría se creó correctamente.", "success")
            return redirect(url_for("admin.categories"), code=303)

    return render_template(
        "admin/create_category.html",
        nombre_label="Nombre de la categoría",
        nombre_maxlength=100,
        nombre_placeholder="Ej. Programación",
        mostrar_descripcion=True,
        boton_texto="Crear categoría",
        cancelar_url=url_for("admin.categories"),
    )


@bp.route("/categories/<int:categoria_id>/edit", methods=["GET", "POST"])
@requiere_admin
def edit_category(categoria_id):
    """Editar una categoría existente."""
    categoria = db.session.get(Categoria, categoria_id)

    if categoria is None:
        flash("La categoría no existe.", "error")
        return redirect(url_for("admin.categories"), code=303)

    if request.method == "POST":
        nombre = request.form.get("nombre", "")
        descripcion = request.form.get("descripcion", "")

        try:
            editar_categoria(categoria_id, nombre, descripcion)
        except ValueError as exc:
            flash(str(exc), "error")
        else:
            flash("La categoría se actualizó correctamente.", "success")
            return redirect(url_for("admin.categories"), code=303)

    return render_template(
        "admin/edit_category.html",
        categoria=categoria,
    )


@bp.get("/tags")
@requiere_admin
def tags():
    """Mostrar las etiquetas disponibles con paginación."""
    busqueda_etiqueta = request.args.get(
        "busqueda_etiqueta", ""
    ).strip()

    pagina = max(1, request.args.get("pagina", 1, type=int))
    por_pagina = 10

    consulta = select(Tag)

    if busqueda_etiqueta:
        consulta = consulta.where(
            Tag.nombre.ilike(f"%{busqueda_etiqueta}%")
        )

    total = db.session.scalar(
        select(db.func.count()).select_from(consulta.subquery())
    )

    total_paginas = max(1, (total + por_pagina - 1) // por_pagina)
    pagina = min(pagina, total_paginas)

    etiquetas = db.session.scalars(
        consulta
        .order_by(Tag.nombre)
        .limit(por_pagina)
        .offset((pagina - 1) * por_pagina)
    ).all()

    return render_template(
        "admin/tags.html",
        etiquetas=etiquetas,
        busqueda_etiqueta=busqueda_etiqueta,
        pagina=pagina,
        total_paginas=total_paginas,
    )

@bp.post("/tags/<int:tag_id>/delete")
@requiere_admin
def delete_tag(tag_id):
    """Eliminar una etiqueta."""
    try:
        eliminar_tag(tag_id)
    except LookupError as exc:
        flash(str(exc), "error")
    else:
        flash("La etiqueta se eliminó correctamente.", "success")

    return redirect(url_for("admin.tags"), code=303)

@bp.route("/tags/new", methods=["GET", "POST"])
@requiere_admin
def create_tag():
    """Crear una etiqueta nueva."""
    if request.method == "POST":
        nombre = request.form.get("nombre", "")

        try:
            crear_tag(nombre)
        except ValueError as exc:
            flash(str(exc), "error")
        else:
            flash("La etiqueta se creó correctamente.", "success")
            return redirect(url_for("admin.tags"), code=303)

    return render_template(
        "admin/create_tag.html",
        nombre_label="Nombre de la etiqueta",
        nombre_maxlength=50,
        nombre_placeholder="Escribí el nombre de la etiqueta...",
        mostrar_descripcion=False,
        boton_texto="Crear etiqueta",
        cancelar_url=url_for("admin.tags"),
    )

@bp.route("/tags/<int:tag_id>/edit", methods=["GET", "POST"])
@requiere_admin
def edit_tag(tag_id):
    """Editar una etiqueta existente."""
    tag = db.session.get(Tag, tag_id)

    if tag is None:
        flash("La etiqueta no existe.", "error")
        return redirect(url_for("admin.tags"), code=303)

    if request.method == "POST":
        nombre = request.form.get("nombre", "")

        try:
            editar_tag(tag_id, nombre)
        except ValueError as exc:
            flash(str(exc), "error")
        else:
            flash("La etiqueta se actualizó correctamente.", "success")
            return redirect(url_for("admin.tags"), code=303)

    return render_template("admin/edit_tag.html", tag=tag)

@bp.post("/activate")
@requiere_sesion
def activate():
    """Solicitar la activación del rol de administrador."""

    usuario = g.usuario_actual

    if usuario.es_admin:
        flash("Tu cuenta ya tiene permisos de administrador.", "success")
        return redirect(url_for("auth.account"), code=303)

    try:
        limitar_intentos("admin_activation", usuario_id=usuario.id)

        activar_administrador(
            usuario,
            request.form.get("codigo_activacion", "")
        )

    except DemasiadosIntentos as exc:
        flash(
            "Hubo demasiados intentos. Esperá unos minutos antes de volver a probar.",
            "error"
        )
        respuesta = redirect(url_for("auth.account"), code=303)
        respuesta.headers["Retry-After"] = str(exc.segundos)
        return respuesta

    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("auth.account"), code=303)

    except RuntimeError:
        flash("La activación no está disponible en este momento.", "error")
        return redirect(url_for("auth.account"), code=303)

    flash("¡Tu cuenta ahora es administradora!", "success")
    return redirect(url_for("auth.account"), code=303)
