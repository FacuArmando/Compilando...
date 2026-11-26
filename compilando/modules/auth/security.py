"""Límites persistentes de intentos y controles HTTP de la aplicación."""

import hashlib
import hmac
import math
from datetime import timedelta
from time import monotonic

from flask import abort, current_app, request
from sqlalchemy import case, delete
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from compilando.extensions import db
from compilando.modules.auth.models import LimiteIntentos, Sesion
from compilando.modules.auth.sessions import ahora_utc


class DemasiadosIntentos(Exception):
    def __init__(self, segundos: int):
        self.segundos = segundos


def limitar_intentos(accion: str, email: str = "", *, usuario_id: int | None = None) -> None:
    """Reservar intentos antes de comprobar contraseñas, incluso con varios procesos."""
    ahora = ahora_utc()
    ventana = current_app.config["AUTH_RATE_WINDOW"]
    secret = current_app.secret_key
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    limites = [(f"{accion}:ip:{request.remote_addr or 'desconocida'}", "AUTH_LOGIN_IP_LIMIT")]
    if accion == "login":
        limites.append((f"login:email:{email.strip().lower()}", "AUTH_LOGIN_EMAIL_LIMIT"))
    elif accion == "password":
        if usuario_id is None:
            raise ValueError("El cambio de contraseña requiere un usuario autenticado.")
        limites[0] = (limites[0][0], "AUTH_PASSWORD_IP_LIMIT")
        limites.append((f"password:usuario:{usuario_id}", "AUTH_PASSWORD_ACCOUNT_LIMIT"))
    elif accion == "ai":
        if usuario_id is None:
            raise ValueError("Consultar IA requiere un usuario autenticado.")
        limites[0] = (limites[0][0], "AI_IP_LIMIT")
        limites.extend(
            [(f"ai:usuario:{usuario_id}", "AI_ACCOUNT_LIMIT"), ("ai:global", "AI_GLOBAL_LIMIT")]
        )
    elif accion == "admin_activation":
        if usuario_id is None:
            raise ValueError("La activación de administrador requiere un usuario autenticado.")
        limites[0] = (limites[0][0], "ADMIN_ACTIVATION_IP_LIMIT")
        limites.append((f"admin_activation:usuario:{usuario_id}", "ADMIN_ACTIVATION_ACCOUNT_LIMIT"))
    else:
        limites[0] = (limites[0][0], "AUTH_REGISTER_IP_LIMIT")

    esperar = 0
    # Esta marca solo limita la limpieza; las decisiones de acceso siguen en DB.
    cleanup_time = monotonic()
    cleanup_due = cleanup_time >= current_app.extensions.get("auth_cleanup_after", 0)
    try:
        if cleanup_due:
            db.session.execute(
                delete(LimiteIntentos).where(LimiteIntentos.inicio_ventana <= ahora - ventana)
            )
            db.session.execute(
                delete(Sesion).where(Sesion.fecha_vencimiento < ahora - timedelta(days=1))
            )
        for identidad, config_key in limites:
            clave = hmac.new(secret, identidad.encode("utf-8"), hashlib.sha256).hexdigest()
            maximo = current_app.config[config_key]
            insert = postgres_insert if db.engine.dialect.name == "postgresql" else sqlite_insert
            expired = LimiteIntentos.inicio_ventana <= ahora - ventana
            incremento = (
                insert(LimiteIntentos)
                .values(clave=clave, inicio_ventana=ahora, intentos=1)
                .on_conflict_do_update(
                    index_elements=[LimiteIntentos.clave],
                    set_={
                        "intentos": case(
                            (expired, 1),
                            (LimiteIntentos.intentos <= maximo, LimiteIntentos.intentos + 1),
                            else_=LimiteIntentos.intentos,
                        ),
                        "inicio_ventana": case(
                            (expired, ahora), else_=LimiteIntentos.inicio_ventana
                        ),
                    },
                )
                .returning(LimiteIntentos.intentos, LimiteIntentos.inicio_ventana)
            )
            intentos, inicio = db.session.execute(incremento).one()
            if intentos > maximo:
                esperar = max(esperar, math.ceil((inicio + ventana - ahora).total_seconds()))
                break
        db.session.commit()
        if cleanup_due:
            current_app.extensions["auth_cleanup_after"] = cleanup_time + min(
                ventana.total_seconds(), 900
            )
    except Exception:
        db.session.rollback()
        raise
    if esperar:
        raise DemasiadosIntentos(max(1, esperar))


def init_app(app) -> None:
    production = app.config["APP_ENV"] == "production"
    secret = app.secret_key
    if not app.testing or production:
        if not isinstance(secret, (str, bytes)) or len(secret) < 32:
            raise RuntimeError(
                "Configurar SECRET_KEY con una clave aleatoria de al menos 32 caracteres."
            )
    if production:
        if not app.config.get("TRUSTED_HOSTS"):
            raise RuntimeError("Configurar TRUSTED_HOSTS con los dominios del despliegue.")
        if not app.config["SESSION_COOKIE_SECURE"] or app.debug:
            raise RuntimeError("Producción requiere cookies Secure y DEBUG deshabilitado.")
        if (
            not app.config["SESSION_COOKIE_HTTPONLY"]
            or app.config["SESSION_COOKIE_SAMESITE"] not in {"Lax", "Strict"}
            or app.config["SESSION_COOKIE_DOMAIN"] is not None
            or app.config["SESSION_COOKIE_PATH"] != "/"
        ):
            raise RuntimeError(
                "Producción requiere cookies HttpOnly, SameSite y limitadas al host."
            )

    @app.before_request
    def proteger_solicitud():
        if production and not request.is_secure:
            abort(400, description="Este servicio requiere HTTPS.")
        if request.endpoint == "auth.change_avatar":
            request.max_content_length = app.config["AVATAR_MAX_BYTES"] + 64 * 1024
            request.max_form_memory_size = 64 * 1024
            request.max_form_parts = 4
        elif request.blueprint in {"auth", "ai"}:
            request.max_content_length = 16 * 1024
            request.max_form_memory_size = 16 * 1024
            request.max_form_parts = 8

    @app.after_request
    def proteger_respuesta(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; object-src 'none'; base-uri 'self'; "
            "frame-ancestors 'none'; form-action 'self'"
        )
        recurso_publico = request.endpoint in {
            "interface_catalog",
            "auth.avatar",
        } and response.status_code in {
            200,
            304,
        }
        if request.endpoint != "static" and not recurso_publico:
            response.headers["Cache-Control"] = "no-store"
        if production and request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response
