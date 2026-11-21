"""Pantallas de acceso, registro y consulta de la cuenta."""

import hmac
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException

from compilando.extensions import db
from compilando.modules.auth.security import DemasiadosIntentos, limitar_intentos
from compilando.modules.auth.services import (
    autenticar_usuario,
    cambiar_contrasena,
    cambiar_email,
    registrar_usuario,
)
from compilando.modules.auth.sessions import cerrar_sesion, iniciar_sesion, requiere_sesion

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _destino_de_regreso(valor: str | None) -> str:
    """Volver solo a pantallas GET conocidas, construyendo de nuevo su URL interna."""
    inicio = url_for("system.index")
    if not valor or len(valor) > 1024 or "\\" in valor or any(c.isspace() for c in valor):
        return inicio
    destinos = {
        "system.index": {"", "question-composer"},
        "questions.view_question": {"", "tu-respuesta"},
        "questions.publish_question": {""},
        "auth.account": {""},
    }
    try:
        ruta = urlsplit(valor)
        if ruta.scheme or ruta.netloc or ruta.query or not ruta.path.startswith("/"):
            return inicio
        endpoint, argumentos = current_app.url_map.bind("").match(ruta.path, method="GET")
    except (ValueError, HTTPException):
        return inicio
    if endpoint not in destinos or ruta.fragment not in destinos[endpoint]:
        return inicio
    return url_for(endpoint, **argumentos, _anchor=ruta.fragment or None)


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Comprobar credenciales y crear una sesión únicamente ante un ingreso válido."""
    regreso = _destino_de_regreso(request.form.get("next", request.args.get("next")))
    if request.method == "GET" and g.usuario_actual is not None:
        return redirect(regreso)
    email = ""
    error = None
    if request.method == "POST":
        email = request.form.get("email", "")
        try:
            limitar_intentos("login", email)
            usuario = autenticar_usuario(email, request.form.get("password", ""))
        except DemasiadosIntentos as exc:
            return formulario_con_limite(
                "auth/login.html", exc, email=email[:254], next_url=regreso
            )
        except ValueError as exc:
            error = str(exc)
        else:
            iniciar_sesion(usuario)
            return redirect(regreso, code=303)
    return render_template(
        "auth/login.html", email=email[:254], error=error, next_url=regreso
    ), 401 if error else 200


@bp.get("/account")
@requiere_sesion
def account():
    """Consultar únicamente los datos del usuario de la sesión validada."""
    return render_template("auth/account.html")


@bp.post("/account/activate-admin")
@requiere_sesion
def activate_admin():
    """Activar permanentemente el rol administrador mediante el código secreto."""

    usuario = g.usuario_actual

    if usuario.es_admin:
        flash("Tu cuenta ya tiene permisos de administrador.", "success")
        return redirect(url_for("auth.account"), code=303)

    codigo_configurado = current_app.config.get("ADMIN_ACTIVATION_CODE", "")

    if not codigo_configurado:
        flash("La activación de administradores no está disponible.", "error")
        return redirect(url_for("auth.account"), code=303)

    try:
        limitar_intentos("admin", usuario_id=usuario.id)
    except DemasiadosIntentos as exc:
        response = make_response(redirect(url_for("auth.account"), code=303))
        response.headers["Retry-After"] = str(exc.segundos)
        flash("Demasiados intentos. Esperá unos minutos antes de volver a probar.", "error")
        return response

    codigo_ingresado = request.form.get("codigo_admin", "")

    if not hmac.compare_digest(
        codigo_ingresado.encode("utf-8"),
        codigo_configurado.encode("utf-8"),
    ):
        flash("El código ingresado no es válido.", "error")
        return redirect(url_for("auth.account"), code=303)

    usuario.es_admin = True
    db.session.commit()

    flash("¡Felicitaciones! Tu cuenta ahora es administradora.", "success")
    return redirect(url_for("auth.account"), code=303)


@bp.post("/account/password")
@requiere_sesion
def change_password():
    """Cambiar únicamente la contraseña de la cuenta validada por la sesión."""
    try:
        limitar_intentos("password", usuario_id=g.usuario_actual.id)
        cambiar_contrasena(
            g.usuario_actual,
            request.form.get("password_actual", ""),
            request.form.get("password_nueva", ""),
            request.form.get("password_confirmacion", ""),
        )
    except DemasiadosIntentos as exc:
        response = make_response(
            render_template(
                "auth/account.html",
                password_error=(
                    "Hubo demasiados intentos. Esperá unos minutos antes de volver a probar."
                ),
            ),
            429,
        )
        response.headers["Retry-After"] = str(exc.segundos)
        return response
    except ValueError as exc:
        return render_template("auth/account.html", password_error=str(exc)), 400

    # La revocación ya se guardó junto con el hash; retirar también la cookie del navegador.
    session.clear()
    flash("Tu contraseña se actualizó. Iniciá sesión con la nueva contraseña.", "success")
    return redirect(url_for("auth.login", next=url_for("auth.account")), code=303)


@bp.post("/account/email")
@requiere_sesion
def change_email():
    """Actualizar el correo de la cuenta validada, confirmando su contraseña actual."""
    nuevo = request.form.get("email_nuevo", "")
    try:
        # Compartir el límite de comprobaciones de contraseña entre cambios de credenciales.
        limitar_intentos("password", usuario_id=g.usuario_actual.id)
        cambiar_email(g.usuario_actual, nuevo, request.form.get("email_password_actual", ""))
    except DemasiadosIntentos as exc:
        response = make_response(
            render_template(
                "auth/account.html",
                email_nuevo=nuevo[:254],
                email_error=(
                    "Hubo demasiados intentos. Esperá unos minutos antes de volver a probar."
                ),
            ),
            429,
        )
        response.headers["Retry-After"] = str(exc.segundos)
        return response
    except ValueError as exc:
        return render_template(
            "auth/account.html", email_nuevo=nuevo[:254], email_error=str(exc)
        ), 400

    session.clear()
    flash(
        "Tu correo se actualizó. Iniciá sesión con el correo nuevo y la misma contraseña.",
        "success",
    )
    return redirect(url_for("auth.login", next=url_for("auth.account")), code=303)


@bp.post("/logout")
def logout():
    """Invalidar la sesión con POST protegido por CSRF."""
    cerrar_sesion()
    return redirect(url_for("system.index"), code=303)


@bp.route("/register", methods=["GET", "POST"])
def register():
    """Mostrar el formulario y registrar una cuenta cuando los datos son válidos."""
    regreso = _destino_de_regreso(request.form.get("next", request.args.get("next")))
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
                "auth/register.html",
                exc,
                username=username[:80],
                email=email[:254],
                next_url=regreso,
            )
        except ValueError as exc:
            error = str(exc)
        else:
            flash("Tu cuenta se creó correctamente.", "success")
            if regreso != url_for("system.index"):
                return redirect(url_for("auth.login", next=regreso), code=303)
            return redirect(url_for("system.index"), code=303)

    return render_template(
        "auth/register.html", username=username, email=email, error=error, next_url=regreso
    ), 400 if error else 200


@bp.errorhandler(CSRFError)
def formulario_invalido(error):
    """Mostrar un formulario nuevo para reintentar un envío vencido o inválido."""
    errores_cuenta = {
        "auth.change_password": "password_error",
        "auth.change_email": "email_error",
    }
    if request.endpoint in errores_cuenta:
        if g.usuario_actual is None:
            return redirect(url_for("auth.login"), code=303)
        campo_error = errores_cuenta[request.endpoint]
        datos = {campo_error: "El formulario venció o no es válido. Volvé a completar los campos."}
        if request.endpoint == "auth.change_email":
            datos["email_nuevo"] = request.form.get("email_nuevo", "")[:254]
        return render_template("auth/account.html", **datos), 400
    template = "auth/register.html" if request.endpoint == "auth.register" else "auth/login.html"
    return render_template(
        template,
        username=request.form.get("username", "")[:80],
        email=request.form.get("email", "")[:254],
        next_url=_destino_de_regreso(request.form.get("next", request.args.get("next"))),
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
