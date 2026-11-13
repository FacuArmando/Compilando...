from datetime import date

from sqlalchemy import Date, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from compilando.extensions import db

class Pregunta(db.Model):
    """Representa una pregunta publicada por un usuario."""

    __tablename__ = "preguntas"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(150), nullable=False)
    cuerpo_detallado: Mapped[str] = mapped_column(Text, nullable = False)
    fecha: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=False
    )

    usuario: Mapped["Usuario"] = relationship("Usuario")