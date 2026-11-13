"""Define los datos de una cuenta de usuario."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from compilando.extensions import db


class Usuario(db.Model):
    """Representa un usuario; la contraseña se guarda como hash."""

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
