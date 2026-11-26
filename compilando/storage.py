"""Archivos pequeños persistentes en PostgreSQL; disco solo para desarrollo local."""

from sqlalchemy import CheckConstraint, ForeignKey, LargeBinary, String, delete, func, select, text
from sqlalchemy.orm import Mapped, mapped_column

from compilando.extensions import db


class Archivo(db.Model):
    __tablename__ = "archivos"
    __table_args__ = (
        CheckConstraint("tamanio > 0", name="tamanio_positivo"),
        CheckConstraint(
            "(usuario_id IS NOT NULL AND pregunta_id IS NULL) OR "
            "(usuario_id IS NULL AND pregunta_id IS NOT NULL)",
            name="un_propietario",
        ),
    )
    clave: Mapped[str] = mapped_column(String(160), primary_key=True)
    contenido: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    tamanio: Mapped[int] = mapped_column(nullable=False)
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    pregunta_id: Mapped[int | None] = mapped_column(
        ForeignKey("preguntas.id", ondelete="CASCADE"), index=True
    )


def usa_base() -> bool:
    from flask import current_app

    return current_app.config["STORAGE_BACKEND"] == "database"


def guardar_blob(clave, contenido, *, usuario_id=None, pregunta_id=None):
    from flask import current_app

    if not contenido or len(contenido) > current_app.config["STORAGE_OBJECT_MAX_BYTES"]:
        raise ValueError("El archivo supera el tamaño permitido para almacenamiento.")
    # Serializar cargas para que dos instancias no excedan simultáneamente el cupo.
    if db.engine.dialect.name == "postgresql":
        db.session.execute(text("SELECT pg_advisory_xact_lock(782361905)"))
    usado = db.session.scalar(select(func.coalesce(func.sum(Archivo.tamanio), 0)))
    if usado + len(contenido) > current_app.config["STORAGE_TOTAL_BYTES"]:
        raise ValueError(
            "El almacenamiento de archivos está lleno. Eliminá archivos antes de subir más."
        )
    db.session.add(
        Archivo(
            clave=clave,
            contenido=contenido,
            tamanio=len(contenido),
            usuario_id=usuario_id,
            pregunta_id=pregunta_id,
        )
    )
    db.session.flush()


def leer_blob(clave):
    return db.session.scalar(select(Archivo.contenido).where(Archivo.clave == clave))


def borrar_blob(clave):
    db.session.execute(delete(Archivo).where(Archivo.clave == clave))


def init_app(app, backend):
    mode = app.config.get("STORAGE_BACKEND") or ("database" if backend == "postgresql" else "local")
    if mode not in {"database", "local"}:
        raise RuntimeError("STORAGE_BACKEND debe ser database o local.")
    if app.config["APP_ENV"] == "production" and not app.testing:
        if backend != "postgresql" or mode != "database":
            raise RuntimeError(
                "Producción requiere PostgreSQL y almacenamiento persistente database."
            )
    app.config["STORAGE_BACKEND"] = mode
