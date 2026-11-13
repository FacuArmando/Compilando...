"""Ciclo de vida de sesiones del servidor y carga de la identidad de cada solicitud."""

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

from flask import current_app, g, request, session
from sqlalchemy import delete, select, update

from compilando.extensions import db
from compilando.modules.auth.models import Sesion, Usuario


def ahora_utc() -> datetime:
    """Usar UTC sin zona en la base para mantener compatibilidad con SQLite."""
    return datetime.now(UTC).replace(tzinfo=None)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _token_actual() -> str | None:
    token = session.get("auth_token")
    if isinstance(token, str) and re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return token
    return None


def iniciar_sesion(usuario: Usuario) -> None:
    """Rotar el identificador y el CSRF; invalidar la sesión anterior del navegador."""
    ahora = ahora_utc()
    token_anterior = _token_actual()
    if token_anterior is not None:
        db.session.execute(
            update(Sesion).where(Sesion.id == _hash_token(token_anterior)).values(activa=False)
        )
    db.session.execute(delete(Sesion).where(Sesion.fecha_vencimiento < ahora - timedelta(days=1)))
    token = secrets.token_urlsafe(32)
    db.session.add(
        Sesion(
            id=_hash_token(token),
            usuario_id=usuario.id,
            fecha_inicio=ahora,
            ultimo_acceso=ahora,
            fecha_vencimiento=ahora + current_app.config["AUTH_SESSION_LIFETIME"],
            activa=True,
        )
    )
    db.session.commit()
    session.clear()
    session["auth_token"] = token
    session.permanent = True


def cerrar_sesion() -> None:
    """Revocar en la base para que una copia de la cookie tampoco pueda reutilizarse."""
    token = _token_actual()
    if token is not None:
        db.session.execute(
            update(Sesion).where(Sesion.id == _hash_token(token)).values(activa=False)
        )
        db.session.commit()
    session.clear()


def init_app(app) -> None:
    @app.before_request
    def cargar_usuario():
        g.usuario_actual = None
        if request.endpoint in {"static", "system.health"}:
            return
        token = _token_actual()
        if token is None:
            if "auth_token" in session:
                session.clear()
            return

        resultado = db.session.execute(
            select(Sesion, Usuario)
            .join(Usuario, Sesion.usuario_id == Usuario.id)
            .where(Sesion.id == _hash_token(token))
            .execution_options(populate_existing=True)
        ).first()
        if resultado is None:
            session.clear()
            return
        sesion, usuario = resultado
        ahora = ahora_utc()
        vencida = (
            sesion.fecha_vencimiento <= ahora
            or sesion.ultimo_acceso + app.config["AUTH_IDLE_TIMEOUT"] <= ahora
        )
        if not sesion.activa or vencida:
            if sesion.activa:
                sesion.activa = False
                db.session.commit()
            session.clear()
            return
        sesion.ultimo_acceso = ahora
        db.session.commit()
        g.usuario_actual = usuario

    @app.context_processor
    def identidad_para_plantillas():
        return {"usuario_actual": g.get("usuario_actual")}
