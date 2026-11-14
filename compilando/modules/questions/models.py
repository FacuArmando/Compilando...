from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from compilando.extensions import db

if TYPE_CHECKING:
    from compilando.modules.categories.models import Categoria
    from compilando.modules.tags.models import Tag
    from compilando.modules.users.models import Usuario

pregunta_tags = db.Table(
    "pregunta_tags",
    db.Column("pregunta_id", db.ForeignKey("preguntas.id"), primary_key=True),
    db.Column("tag_id", db.ForeignKey("tags.id"), primary_key=True),
)


class Pregunta(db.Model):
    """Representa una pregunta publicada por un usuario."""

    __tablename__ = "preguntas"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(150), nullable=False)
    cuerpo_detallado: Mapped[str] = mapped_column(Text, nullable=False)
    fecha: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)

    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)

    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"), nullable=False)

    usuario: Mapped["Usuario"] = relationship("Usuario")
    categoria: Mapped["Categoria"] = relationship("Categoria")
    tags: Mapped[list["Tag"]] = relationship("Tag", secondary=pregunta_tags)
