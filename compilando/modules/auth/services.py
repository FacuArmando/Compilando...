"""Registro, comprobación y cambio de credenciales, independientes de los formularios."""

import re
import secrets

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from compilando.extensions import db
from compilando.modules.auth.models import Sesion, Usuario

ERROR_CREDENCIALES = "Credenciales incorrectas."
# Se genera una sola vez; evita omitir el costo del hash cuando el correo no existe.
_HASH_FICTICIO = generate_password_hash(secrets.token_urlsafe(32))


def autenticar_usuario(email: str, password: str) -> Usuario:
    """Comprobar credenciales sin revelar si existe una cuenta ni cambiar su clave."""
    email = email.strip().lower()
    # Conservar el acceso de las cuentas creadas antes del máximo de 18 caracteres.
    if not email or len(email) > 254 or not 1 <= len(password) <= 128:
        raise ValueError(ERROR_CREDENCIALES)

    usuario = db.session.scalar(select(Usuario).where(Usuario.email == email))
    password_hash = usuario.password_hash if usuario is not None else _HASH_FICTICIO
    coincide = check_password_hash(password_hash, password)
    if usuario is None or not coincide:
        raise ValueError(ERROR_CREDENCIALES)
    return usuario


def cambiar_contrasena(usuario: Usuario, actual: str, nueva: str, confirmacion: str) -> None:
    """Cambiar el hash y revocar todas las sesiones de la cuenta en una sola transacción."""
    if not actual or not nueva or not confirmacion:
        raise ValueError("Completá la contraseña actual, la nueva y su confirmación.")
    if not 1 <= len(actual) <= 128:
        raise ValueError("La contraseña actual no es correcta.")
    if not 8 <= len(nueva) <= 18 or not nueva.strip():
        raise ValueError("La nueva contraseña debe tener entre 8 y 18 caracteres.")
    if nueva != confirmacion:
        raise ValueError("La nueva contraseña y su confirmación no coinciden.")

    # Leer el hash vigente, sin depender de la copia cargada al iniciar la solicitud.
    hash_actual = db.session.scalar(select(Usuario.password_hash).where(Usuario.id == usuario.id))
    if hash_actual is None or not check_password_hash(hash_actual, actual):
        raise ValueError("La contraseña actual no es correcta.")
    if actual == nueva:
        raise ValueError("Elegí una contraseña diferente de la actual.")

    nuevo_hash = generate_password_hash(nueva)
    try:
        resultado = db.session.execute(
            update(Usuario)
            .where(Usuario.id == usuario.id, Usuario.password_hash == hash_actual)
            .values(password_hash=nuevo_hash)
            .execution_options(synchronize_session=False)
        )
        if resultado.rowcount != 1:
            raise ValueError("La contraseña cambió mientras guardabas. Volvé a iniciar sesión.")
        db.session.execute(
            update(Sesion).where(Sesion.usuario_id == usuario.id).values(activa=False)
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def cambiar_email(usuario: Usuario, nuevo: str, actual: str) -> None:
    """Cambiar el correo de la cuenta autenticada y revocar sus sesiones al guardar."""
    nuevo = nuevo.strip().lower()
    if not nuevo or not actual:
        raise ValueError("Completá el correo nuevo y tu contraseña actual.")
    if len(nuevo) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", nuevo):
        raise ValueError("Ingresá un correo electrónico válido.")
    if not 1 <= len(actual) <= 128:
        raise ValueError("La contraseña actual no es correcta.")

    cuenta = db.session.execute(
        select(Usuario.email, Usuario.password_hash).where(Usuario.id == usuario.id)
    ).first()
    if cuenta is None or not check_password_hash(cuenta.password_hash, actual):
        raise ValueError("La contraseña actual no es correcta.")
    if nuevo == cuenta.email.lower():
        raise ValueError("Ingresá un correo diferente del actual.")
    if db.session.scalar(select(Usuario.id).where(func.lower(Usuario.email) == nuevo)) is not None:
        raise ValueError("Ese correo electrónico ya está registrado.")

    try:
        resultado = db.session.execute(
            update(Usuario)
            .where(
                Usuario.id == usuario.id,
                Usuario.email == cuenta.email,
                Usuario.password_hash == cuenta.password_hash,
            )
            .values(email=nuevo)
            .execution_options(synchronize_session=False)
        )
        if resultado.rowcount != 1:
            raise ValueError("Los datos de tu cuenta cambiaron. Volvé a iniciar sesión.")
        db.session.execute(
            update(Sesion).where(Sesion.usuario_id == usuario.id).values(activa=False)
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        # La base resuelve también dos cambios que intentan reservar el mismo correo.
        if (
            db.session.scalar(select(Usuario.id).where(func.lower(Usuario.email) == nuevo))
            is not None
        ):
            raise ValueError("Ese correo electrónico ya está registrado.") from None
        raise
    except Exception:
        db.session.rollback()
        raise


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
    if not 8 <= len(password) <= 18:
        raise ValueError("La contraseña debe tener entre 8 y 18 caracteres.")

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
