"""Registro y comprobación de credenciales, independientes de los formularios."""

import re
import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from compilando.extensions import db
from compilando.modules.auth.models import Usuario

ERROR_CREDENCIALES = "Credenciales incorrectas."
# Se genera una sola vez; evita omitir el costo del hash cuando el correo no existe.
_HASH_FICTICIO = generate_password_hash(secrets.token_urlsafe(32))


def autenticar_usuario(email: str, password: str) -> Usuario:
    """Comprobar credenciales sin revelar si existe una cuenta ni cambiar su clave."""
    email = email.strip().lower()
    if not email or len(email) > 254 or not 1 <= len(password) <= 128:
        raise ValueError(ERROR_CREDENCIALES)

    usuario = db.session.scalar(select(Usuario).where(Usuario.email == email))
    password_hash = usuario.password_hash if usuario is not None else _HASH_FICTICIO
    coincide = check_password_hash(password_hash, password)
    if usuario is None or not coincide:
        raise ValueError(ERROR_CREDENCIALES)
    return usuario


def registrar_usuario(username: str, email: str, password: str) -> Usuario:
    """Validar y guardar una cuenta; lanzar ValueError ante datos inválidos o repetidos."""
    username = username.strip()
    email = email.strip().lower()

    if not username or not email or not password.strip():
        raise ValueError("Completá el nombre de usuario, el correo y la contraseña.")
    if len(username) > 80:
        raise ValueError("El nombre de usuario debe tener como máximo 80 caracteres.")
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValueError("Ingresá un correo electrónico válido.")
    if not 8 <= len(password) <= 128:
        raise ValueError("La contraseña debe tener entre 8 y 128 caracteres.")

    usuario = Usuario(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
    )
    db.session.add(usuario)

    try:
        db.session.commit()
    except IntegrityError:
        # La base garantiza la unicidad, incluso si dos registros llegan a la vez.
        db.session.rollback()
        if db.session.scalar(select(Usuario.id).where(Usuario.username == username)) is not None:
            raise ValueError("Ese nombre de usuario ya está registrado.") from None
        if db.session.scalar(select(Usuario.id).where(Usuario.email == email)) is not None:
            raise ValueError("Ese correo electrónico ya está registrado.") from None
        raise

    return usuario
