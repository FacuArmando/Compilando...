"""Cuentas, sesiones revocables y contadores de acceso. Fechas guardadas en UTC."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from compilando.extensions import db


class Usuario(db.Model):
    """Representa un usuario; la contraseña se guarda como hash."""

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)


class Sesion(db.Model):
    """Guarda el hash del identificador; el token original solo va en la cookie."""

    __tablename__ = "sesiones"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    fecha_inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fecha_vencimiento: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ultimo_acceso: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False)


class LimiteIntentos(db.Model):
    """Comparte los límites entre procesos sin conservar correos o IP en claro."""

    __tablename__ = "limites_autenticacion"

    clave: Mapped[str] = mapped_column(String(64), primary_key=True)
    inicio_ventana: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False)
