from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from compilando.extensions import db

if TYPE_CHECKING:
    from compilando.modules.questions.models import Pregunta


class Tag(db.Model):
    """Representa una etiqueta que puede asociarse a una pregunta."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    preguntas: Mapped[list["Pregunta"]] = relationship("Pregunta", secondary="pregunta_tags")
