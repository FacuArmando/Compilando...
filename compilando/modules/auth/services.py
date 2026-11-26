"""Registro, comprobación y cambio de credenciales, independientes de los formularios."""

import re
import secrets
from datetime import date
from pathlib import Path
from uuid import uuid4

from flask import current_app
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError
from werkzeug.datastructures import FileStorage
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

    try:
        usuario = db.session.scalar(
            insert(Usuario)
            .values(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
            )
            .returning(Usuario)
        )
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


def cambiar_username(usuario: Usuario, nuevo: str) -> None:
    """Cambiar el nombre de usuario de la cuenta autenticada."""
    nuevo = nuevo.strip()
    if not nuevo:
        raise ValueError("Completá el nuevo nombre de usuario.")
    if len(nuevo) > 80:
        raise ValueError("El nombre de usuario debe tener como máximo 80 caracteres.")

    actual = db.session.scalar(select(Usuario.username).where(Usuario.id == usuario.id))
    if actual is None:
        raise ValueError("Los datos de tu cuenta cambiaron. Volvé a iniciar sesión.")
    if nuevo == actual:
        raise ValueError("Elegí un nombre de usuario diferente del actual.")
    if db.session.scalar(select(Usuario.id).where(Usuario.username == nuevo)) is not None:
        raise ValueError("Ese nombre de usuario ya está registrado.")

    try:
        resultado = db.session.execute(
            update(Usuario)
            .where(Usuario.id == usuario.id, Usuario.username == actual)
            .values(username=nuevo)
            .execution_options(synchronize_session=False)
        )
        if resultado.rowcount != 1:
            raise ValueError("Los datos de tu cuenta cambiaron. Volvé a iniciar sesión.")
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if db.session.scalar(select(Usuario.id).where(Usuario.username == nuevo)) is not None:
            raise ValueError("Ese nombre de usuario ya está registrado.") from None
        raise
    except Exception:
        db.session.rollback()
        raise


def _extension_imagen_valida(contenido: bytes) -> str | None:
    """Verificar la firma binaria real de la imagen sin confiar en el navegador."""
    if contenido.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if contenido.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if len(contenido) >= 12 and contenido[:4] == b"RIFF" and contenido[8:12] == b"WEBP":
        return ".webp"
    return None


def ruta_avatar(nombre_archivo: str) -> Path:
    carpeta = Path(current_app.config["AVATAR_UPLOAD_FOLDER"]).resolve()
    ruta = (carpeta / nombre_archivo).resolve()
    if ruta.parent != carpeta:
        raise ValueError("Ruta de avatar inválida.")
    return ruta


def cambiar_avatar(usuario: Usuario, archivo: FileStorage | None) -> None:
    """Validar y guardar la foto de perfil del usuario autenticado."""
    if archivo is None or not archivo.filename:
        raise ValueError("Seleccioná una imagen para tu foto de perfil.")

    max_bytes = current_app.config["AVATAR_MAX_BYTES"]
    contenido = archivo.stream.read(max_bytes + 1)
    if not contenido:
        raise ValueError("El archivo de imagen está vacío.")
    if len(contenido) > max_bytes:
        raise ValueError("La imagen no puede superar los 2 MB.")

    extension = _extension_imagen_valida(contenido)
    if extension is None:
        raise ValueError("Elegí una imagen válida en formato JPG, PNG o WebP.")

    nuevo_nombre = f"{uuid4().hex}{extension}"
    destino = ruta_avatar(nuevo_nombre)
    destino.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    anterior = db.session.scalar(select(Usuario.avatar_filename).where(Usuario.id == usuario.id))

    try:
        with destino.open("xb") as f:
            destino.chmod(0o600)
            f.write(contenido)

        resultado = db.session.execute(
            update(Usuario)
            .where(Usuario.id == usuario.id)
            .values(avatar_filename=nuevo_nombre)
            .execution_options(synchronize_session=False)
        )
        if resultado.rowcount != 1:
            destino.unlink(missing_ok=True)
            raise ValueError("Los datos de tu cuenta cambiaron. Volvé a iniciar sesión.")
        db.session.commit()
    except Exception:
        destino.unlink(missing_ok=True)
        db.session.rollback()
        raise

    if anterior:
        try:
            ruta_avatar(anterior).unlink(missing_ok=True)
        except ValueError:
            pass


def eliminar_avatar(usuario: Usuario) -> None:
    """Quitar la foto de perfil actual y volver al avatar con inicial."""
    anterior = db.session.scalar(select(Usuario.avatar_filename).where(Usuario.id == usuario.id))
    if not anterior:
        raise ValueError("No tenés una foto de perfil cargada.")

    db.session.execute(
        update(Usuario)
        .where(Usuario.id == usuario.id)
        .values(avatar_filename=None)
        .execution_options(synchronize_session=False)
    )
    db.session.commit()

    try:
        ruta_avatar(anterior).unlink(missing_ok=True)
    except ValueError:
        pass


def actualizar_perfil(usuario: Usuario, bio: str, fecha_nacimiento_str: str) -> None:
    """Validar y guardar la descripción personal y fecha de cumpleaños del usuario."""
    bio_limpia = (bio or "").strip()
    if len(bio_limpia) > 280:
        raise ValueError("La descripción debe tener como máximo 280 caracteres.")

    fecha_nac: date | None = None
    fecha_str = (fecha_nacimiento_str or "").strip()
    if fecha_str:
        try:
            fecha_nac = date.fromisoformat(fecha_str)
        except ValueError:
            raise ValueError("Ingresá una fecha de cumpleaños válida.") from None
        hoy = date.today()
        if fecha_nac > hoy or fecha_nac.year < 1900:
            raise ValueError("Ingresá una fecha de cumpleaños válida.")

    try:
        resultado = db.session.execute(
            update(Usuario)
            .where(Usuario.id == usuario.id)
            .values(bio=bio_limpia or None, fecha_nacimiento=fecha_nac)
            .execution_options(synchronize_session=False)
        )
        if resultado.rowcount != 1:
            raise ValueError("Los datos de tu cuenta cambiaron. Volvé a iniciar sesión.")
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def obtener_estadisticas_usuario(usuario_id: int) -> dict[str, int]:
    """Calcular métricas de participación del usuario en la comunidad."""
    from compilando.modules.answers.models import EstadoRespuesta, Respuesta
    from compilando.modules.questions.models import Pregunta

    preguntas = select(func.count(Pregunta.id)).where(Pregunta.usuario_id == usuario_id)

    personas = (
        select(func.count(func.distinct(Respuesta.usuario_id)))
        .join(Pregunta, Respuesta.pregunta_id == Pregunta.id)
        .where(
            Pregunta.usuario_id == usuario_id,
            Respuesta.es_ia.is_(False),
            Respuesta.usuario_id.is_not(None),
            Respuesta.usuario_id != usuario_id,
        )
    )

    totales = select(func.count(Respuesta.id)).where(
        Respuesta.usuario_id == usuario_id,
        Respuesta.es_ia.is_(False),
    )

    aceptadas = select(func.count(Respuesta.id)).where(
        Respuesta.usuario_id == usuario_id,
        Respuesta.es_ia.is_(False),
        Respuesta.estado == EstadoRespuesta.ACEPTADA.value,
    )
    preguntas_realizadas, personas_respondieron, respuestas_totales, respuestas_aceptadas = (
        db.session.execute(
            select(
                preguntas.scalar_subquery(),
                personas.scalar_subquery(),
                totales.scalar_subquery(),
                aceptadas.scalar_subquery(),
            )
        ).one()
    )

    porcentaje_aceptadas = (
        round((respuestas_aceptadas / respuestas_totales) * 100) if respuestas_totales > 0 else 0
    )

    return {
        "preguntas_realizadas": preguntas_realizadas,
        "personas_respondieron": personas_respondieron,
        "respuestas_aceptadas": respuestas_aceptadas,
        "respuestas_totales": respuestas_totales,
        "porcentaje_aceptadas": porcentaje_aceptadas,
    }


def es_cumpleanos_hoy(usuario: Usuario) -> bool:
    """Comprobar si hoy coincide con el día y mes de nacimiento del usuario."""
    fecha_nac = getattr(usuario, "fecha_nacimiento", None)
    if fecha_nac is None:
        return False
    hoy = date.today()
    return fecha_nac.month == hoy.month and fecha_nac.day == hoy.day


def edad_usuario_hoy(usuario: Usuario) -> int | None:
    """Calcular los años que cumple el usuario según su fecha de nacimiento."""
    fecha_nac = getattr(usuario, "fecha_nacimiento", None)
    if fecha_nac is None:
        return None
    hoy = date.today()
    edad = hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))
    return max(edad, 1)
