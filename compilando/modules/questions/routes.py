
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy import select

from compilando.extensions import db
from compilando.modules.categories.models import Categoria
from compilando.modules.questions.services import publicar_pregunta
from compilando.modules.tags.models import Tag

bp = Blueprint("questions", __name__)


@bp.route("/questions/publish", methods=["GET", "POST"])
def publish_question():

    if g.usuario_actual is None:
        abort(401)

    #Valores iniciales para mostrar el formulario vacío
    titulo = ""
    cuerpo = ""
    categoria_nombre = ""
    tags_texto = ""
    error_titulo = False
    error_cuerpo = False
    error_categoria = False

    if request.method == "POST":

        titulo = request.form.get("titulo", "")
        cuerpo = request.form.get("cuerpo", "")
        categoria_nombre = request.form.get("categoria", "")
        tags_texto = request.form.get("tags", "")
        nombres_tags = tags_texto.split(",")

        try:
            publicar_pregunta(
                titulo=titulo,
                cuerpo=cuerpo,
                categoria_nombre=categoria_nombre,
                nombres_tags=nombres_tags,
                usuario=g.usuario_actual
            )

            return redirect(url_for("questions.publish_success"))

        except ValueError as error:
            mensaje = str(error).lower()

            error_titulo = "título" in mensaje
            error_cuerpo = "cuerpo" in mensaje
            error_categoria = "categoría" in mensaje

            if not error_titulo and not error_cuerpo and not error_categoria:
                flash(str(error), "error")

    #Estas consultas se ejecutan tanto para GET como para POST
    categorias = db.session.scalars(
        select(Categoria).order_by(Categoria.nombre)
    ).all()

    tags = db.session.scalars(
        select(Tag).order_by(Tag.nombre)
    ).all()

    return render_template(
        "questions/publish_question.html",
        categorias=categorias,
        tags=tags,
        titulo=titulo,
        cuerpo=cuerpo,
        categoria_nombre=categoria_nombre,
        tags_texto=tags_texto,
        error_titulo=error_titulo,
        error_cuerpo=error_cuerpo,
        error_categoria=error_categoria
    )


@bp.get("/questions/publish/success")
def publish_success():
    return render_template("questions/publish_success.html")
