"""Una pregunta puede guardarse una sola vez por usuario."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from compilando.extensions import db

if TYPE_CHECKING:
    from compilando.modules.questions.models import Pregunta


def ahora_utc():
    return datetime.now(UTC).replace(tzinfo=None)


class PreguntaGuardada(db.Model):
    __tablename__ = "preguntas_guardadas"
    __table_args__ = (Index("ix_guardadas_usuario_fecha", "usuario_id", "fecha", "pregunta_id"),)

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True
    )
    pregunta_id: Mapped[int] = mapped_column(
        ForeignKey("preguntas.id", ondelete="CASCADE"), primary_key=True
    )
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora_utc, nullable=False)
    pregunta: Mapped["Pregunta"] = relationship(back_populates="guardados")
