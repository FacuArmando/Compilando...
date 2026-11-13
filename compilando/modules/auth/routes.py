"""Pantallas de registro e inicio de sesión."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError

from compilando.modules.auth.services import registrar_usuario

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/register", methods=["GET", "POST"])
def register():
    """Mostrar el formulario y registrar una cuenta cuando los datos son válidos."""
    username = ""
    email = ""
    error = None

    if request.method == "POST":
        username = request.form.get("username", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        try:
            registrar_usuario(username, email, password)
        except ValueError as exc:
            error = str(exc)
        else:
            flash("Tu cuenta se creó correctamente.", "success")
            return redirect(url_for("system.index"), code=303)

    return render_template(
        "auth/register.html", username=username, email=email, error=error
    ), 400 if error else 200


@bp.errorhandler(CSRFError)
def registro_con_formulario_invalido(error):
    """Mostrar un formulario nuevo para reintentar un envío vencido o inválido."""
    return render_template(
        "auth/register.html",
        username=request.form.get("username", ""),
        email=request.form.get("email", ""),
        error="El formulario venció o no es válido. Revisá los datos y volvé a enviarlo.",
    ), 400
