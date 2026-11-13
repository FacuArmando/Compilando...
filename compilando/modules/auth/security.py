"""Límites persistentes de intentos y controles HTTP de la aplicación."""

import hashlib
import hmac
import math

from flask import abort, current_app, request
from sqlalchemy import case, delete, update
from sqlalchemy.exc import IntegrityError

from compilando.extensions import db
from compilando.modules.auth.models import LimiteIntentos
from compilando.modules.auth.sessions import ahora_utc


class DemasiadosIntentos(Exception):
    def __init__(self, segundos: int):
        self.segundos = segundos


def limitar_intentos(accion: str, email: str = "") -> None:
    """Reservar intentos antes de comprobar contraseñas, incluso con varios procesos."""
    ahora = ahora_utc()
    ventana = current_app.config["AUTH_RATE_WINDOW"]
    secret = current_app.secret_key
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    limites = [(f"{accion}:ip:{request.remote_addr or 'desconocida'}", "AUTH_LOGIN_IP_LIMIT")]
    if accion == "login":
        limites.append((f"login:email:{email.strip().lower()}", "AUTH_LOGIN_EMAIL_LIMIT"))
    else:
        limites[0] = (limites[0][0], "AUTH_REGISTER_IP_LIMIT")

    esperar = 0
    try:
        db.session.execute(
            delete(LimiteIntentos).where(LimiteIntentos.inicio_ventana <= ahora - ventana)
        )
        for identidad, config_key in limites:
            clave = hmac.new(secret, identidad.encode("utf-8"), hashlib.sha256).hexdigest()
            maximo = current_app.config[config_key]
            incremento = (
                update(LimiteIntentos)
                .where(LimiteIntentos.clave == clave)
                .values(
                    intentos=case(
                        (LimiteIntentos.intentos <= maximo, LimiteIntentos.intentos + 1),
                        else_=LimiteIntentos.intentos,
                    )
                )
                .returning(LimiteIntentos.intentos, LimiteIntentos.inicio_ventana)
            )
            resultado = db.session.execute(incremento).first()
            if resultado is None:
                try:
                    with db.session.begin_nested():
                        db.session.add(
                            LimiteIntentos(clave=clave, inicio_ventana=ahora, intentos=1)
                        )
                        db.session.flush()
                    resultado = (1, ahora)
                except IntegrityError:
                    # Otro proceso creó el mismo contador mientras se lo consultaba.
                    resultado = db.session.execute(incremento).one()
            intentos, inicio = resultado
            if intentos > maximo:
                esperar = max(esperar, math.ceil((inicio + ventana - ahora).total_seconds()))
                break
        db.session.commit()
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
        if request.blueprint == "auth":
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
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        if production and request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response
