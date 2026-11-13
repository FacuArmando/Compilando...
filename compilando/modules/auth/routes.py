"""Pantallas de registro e inicio de sesión."""

from flask import Blueprint, flash, g, make_response, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError

from compilando.modules.auth.security import DemasiadosIntentos, limitar_intentos
from compilando.modules.auth.services import autenticar_usuario, registrar_usuario
from compilando.modules.auth.sessions import cerrar_sesion, iniciar_sesion

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Comprobar credenciales y crear una sesión únicamente ante un ingreso válido."""
    if request.method == "GET" and g.usuario_actual is not None:
        return redirect(url_for("system.index"))
    email = ""
    error = None
    if request.method == "POST":
        email = request.form.get("email", "")
        try:
            limitar_intentos("login", email)
            usuario = autenticar_usuario(email, request.form.get("password", ""))
        except DemasiadosIntentos as exc:
            return formulario_con_limite("auth/login.html", exc, email=email[:254])
        except ValueError as exc:
            error = str(exc)
        else:
            iniciar_sesion(usuario)
            return redirect(url_for("system.index"), code=303)
    return render_template("auth/login.html", email=email[:254], error=error), 401 if error else 200


@bp.post("/logout")
def logout():
    """Invalidar la sesión con POST protegido por CSRF."""
    cerrar_sesion()
    return redirect(url_for("system.index"), code=303)


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
            limitar_intentos("register")
            registrar_usuario(username, email, password)
        except DemasiadosIntentos as exc:
            return formulario_con_limite(
                "auth/register.html", exc, username=username[:80], email=email[:254]
            )
        except ValueError as exc:
            error = str(exc)
        else:
            flash("Tu cuenta se creó correctamente.", "success")
            return redirect(url_for("system.index"), code=303)

    return render_template(
        "auth/register.html", username=username, email=email, error=error
    ), 400 if error else 200


@bp.errorhandler(CSRFError)
def formulario_invalido(error):
    """Mostrar un formulario nuevo para reintentar un envío vencido o inválido."""
    template = "auth/register.html" if request.endpoint == "auth.register" else "auth/login.html"
    return render_template(
        template,
        username=request.form.get("username", "")[:80],
        email=request.form.get("email", "")[:254],
        error="El formulario venció o no es válido. Revisá los datos y volvé a enviarlo.",
    ), 400


def formulario_con_limite(template, error, **campos):
    response = make_response(
        render_template(
            template,
            error="Hubo demasiados intentos. Esperá unos minutos antes de volver a probar.",
            **campos,
        ),
        429,
    )
    response.headers["Retry-After"] = str(error.segundos)
    return response
