"""Pantallas de acceso, registro y consulta de la cuenta."""

from io import BytesIO
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException

from compilando.modules.auth.security import DemasiadosIntentos, limitar_intentos
from compilando.modules.auth.services import (
    actualizar_perfil,
    autenticar_usuario,
    cambiar_avatar,
    cambiar_contrasena,
    cambiar_email,
    cambiar_username,
    eliminar_avatar,
    es_cumpleanos_hoy,
    nombre_miniatura_avatar,
    obtener_estadisticas_usuario,
    registrar_usuario,
    ruta_avatar,
)
from compilando.modules.auth.sessions import cerrar_sesion, iniciar_sesion, requiere_sesion
from compilando.storage import leer_blob, usa_base

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
        "saved.index": {""},
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


def _render_account(status: int = 200, **contexto):
    usuario = g.usuario_actual
    datos = {
        "estadisticas": obtener_estadisticas_usuario(usuario.id),
        "es_cumpleanos": es_cumpleanos_hoy(usuario),
        **contexto,
    }
    return render_template("auth/account.html", **datos), status


@bp.get("/account")
@requiere_sesion
def account():
    """Consultar únicamente los datos del usuario de la sesión validada."""
    return _render_account()


@bp.get("/account/stats")
@requiere_sesion
def account_stats():
    """Devolver estadísticas actualizadas en JSON para refrescar la vista en vivo."""
    return jsonify(obtener_estadisticas_usuario(g.usuario_actual.id))


@bp.post("/account/profile")
@requiere_sesion
def update_profile():
    """Actualizar la descripción personal y el cumpleaños de la cuenta."""
    bio = request.form.get("bio", "")
    fecha_nacimiento = request.form.get("fecha_nacimiento", "")
    try:
        limitar_intentos("profile", usuario_id=g.usuario_actual.id)
        actualizar_perfil(g.usuario_actual, bio, fecha_nacimiento)
    except DemasiadosIntentos as exc:
        body, _ = _render_account(
            429,
            bio_valor=bio[:280],
            fecha_nacimiento_valor=fecha_nacimiento[:10],
            profile_error=(
                "Hubo demasiados intentos. Esperá unos minutos antes de volver a probar."
            ),
        )
        response = make_response(body, 429)
        response.headers["Retry-After"] = str(exc.segundos)
        return response
    except ValueError as exc:
        return _render_account(
            400,
            bio_valor=bio[:280],
            fecha_nacimiento_valor=fecha_nacimiento[:10],
            profile_error=str(exc),
        )

    flash("Tu perfil se actualizó.", "success")
    return redirect(url_for("auth.account"), code=303)


@bp.post("/account/username")
@requiere_sesion
def change_username():
    """Actualizar el nombre de usuario de la cuenta validada por la sesión."""
    nuevo = request.form.get("username_nuevo", "")
    try:
        limitar_intentos("username", usuario_id=g.usuario_actual.id)
        cambiar_username(g.usuario_actual, nuevo)
    except DemasiadosIntentos as exc:
        response = make_response(
            render_template(
                "auth/account.html",
                username_nuevo=nuevo[:80],
                username_error=(
                    "Hubo demasiados intentos. Esperá unos minutos antes de volver a probar."
                ),
            ),
            429,
        )
        response.headers["Retry-After"] = str(exc.segundos)
        return response
    except ValueError as exc:
        return render_template(
            "auth/account.html", username_nuevo=nuevo[:80], username_error=str(exc)
        ), 400

    flash("Tu nombre de usuario se actualizó.", "success")
    return redirect(url_for("auth.account"), code=303)


@bp.get("/avatar/<nombre>")
def avatar(nombre: str):
    """Servir la foto de perfil almacenada de forma segura (miniatura o ampliada)."""
    if not nombre or "/" in nombre or "\\" in nombre or ".." in nombre:
        return "", 404
    tamano = request.args.get("size", "full").strip().lower()
    if usa_base():
        contenido = None
        if tamano == "thumb":
            contenido = leer_blob("avatars/" + nombre_miniatura_avatar(nombre))
        if contenido is None:
            contenido = leer_blob("avatars/" + nombre)
        if contenido is None:
            return "", 404
        return send_file(BytesIO(contenido), download_name=nombre, conditional=True, max_age=3600)
    try:
        ruta = ruta_avatar(nombre)
        if tamano == "thumb":
            ruta_thumb = ruta_avatar(nombre_miniatura_avatar(nombre))
            if ruta_thumb.is_file():
                ruta = ruta_thumb
    except ValueError:
        return "", 404
    if not ruta.is_file():
        return "", 404
    return send_file(ruta, conditional=True, max_age=3600)


@bp.post("/account/avatar")
@requiere_sesion
def change_avatar():
    """Subir o actualizar la foto de perfil de la cuenta autenticada."""
    try:
        limitar_intentos("avatar", usuario_id=g.usuario_actual.id)
        cambiar_avatar(g.usuario_actual, request.files.get("avatar"))
    except DemasiadosIntentos as exc:
        body, _ = _render_account(
            429,
            avatar_error=(
                "Hubo demasiados intentos. Esperá unos minutos antes de volver a probar."
            ),
        )
        response = make_response(body, 429)
        response.headers["Retry-After"] = str(exc.segundos)
        return response
    except ValueError as exc:
        return _render_account(400, avatar_error=str(exc))

    flash("Tu foto de perfil se actualizó.", "success")
    return redirect(url_for("auth.account"), code=303)


@bp.post("/account/avatar/delete")
@requiere_sesion
def delete_avatar():
    """Eliminar la foto de perfil actual del usuario."""
    try:
        eliminar_avatar(g.usuario_actual)
    except ValueError as exc:
        return _render_account(400, avatar_error=str(exc))

    flash("Tu foto de perfil se eliminó.", "success")
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
    """Registrar la cuenta e iniciar sesión cuando los datos son válidos."""
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
            usuario = registrar_usuario(username, email, password)
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
            iniciar_sesion(usuario)
            flash("Tu cuenta se creó correctamente.", "success")
            return redirect(regreso, code=303)

    return render_template(
        "auth/register.html", username=username, email=email, error=error, next_url=regreso
    ), 400 if error else 200


@bp.errorhandler(CSRFError)
def formulario_invalido(error):
    """Mostrar un formulario nuevo para reintentar un envío vencido o inválido."""
    errores_cuenta = {
        "auth.change_password": "password_error",
        "auth.change_email": "email_error",
        "auth.change_username": "username_error",
        "auth.change_avatar": "avatar_error",
        "auth.delete_avatar": "avatar_error",
        "auth.update_profile": "profile_error",
    }
    if request.endpoint in errores_cuenta:
        if g.usuario_actual is None:
            return redirect(url_for("auth.login"), code=303)
        campo_error = errores_cuenta[request.endpoint]
        datos = {campo_error: "El formulario venció o no es válido. Volvé a completar los campos."}
        if request.endpoint == "auth.change_email":
            datos["email_nuevo"] = request.form.get("email_nuevo", "")[:254]
        if request.endpoint == "auth.change_username":
            datos["username_nuevo"] = request.form.get("username_nuevo", "")[:80]
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


@bp.errorhandler(413)
def archivo_demasiado_grande(error):
    """Mostrar mensaje claro si la foto supera el límite máximo permitido."""
    if request.endpoint == "auth.change_avatar":
        if g.usuario_actual is None:
            return redirect(url_for("auth.login"), code=303)
        maximo = current_app.config["AVATAR_MAX_BYTES"] // (1024 * 1024)
        return _render_account(
            413,
            avatar_error=f"La imagen no puede superar los {maximo} MB.",
        )
    return error
