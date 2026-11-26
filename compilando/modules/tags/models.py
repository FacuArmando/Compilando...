from typing import TYPE_CHECKING

from sqlalchemy import String, Text, event, inspect
from sqlalchemy.orm import Mapped, mapped_column, relationship

from compilando.extensions import db
from compilando.search_text import normalizar_busqueda

if TYPE_CHECKING:
    from compilando.modules.questions.models import Pregunta


class Tag(db.Model):
    """Representa una etiqueta que puede asociarse a una pregunta."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    nombre_busqueda: Mapped[str] = mapped_column(Text, deferred=True, default="")

    preguntas: Mapped[list["Pregunta"]] = relationship(
        "Pregunta", secondary="pregunta_tags", back_populates="tags"
    )


@event.listens_for(Tag, "before_insert")
@event.listens_for(Tag, "before_update")
def actualizar_texto_busqueda(mapper, connection, tag):
    state = inspect(tag)
    if state.pending or state.attrs.nombre.history.has_changes():
        tag.nombre_busqueda = normalizar_busqueda(tag.nombre)
