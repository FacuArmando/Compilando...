from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, query_expression, relationship

from compilando.extensions import db

if TYPE_CHECKING:
    from compilando.modules.answers.models import Respuesta
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
    __table_args__ = (
        Index("ix_preguntas_fecha_id", "fecha", "id"),
        Index("ix_preguntas_categoria_fecha_id", "categoria_id", "fecha", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(150), nullable=False)
    cuerpo_detallado: Mapped[str] = mapped_column(Text, nullable=False)
    fecha: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    # Valor calculado del listado; no agrega columnas ni requiere migración.
    cantidad_respuestas_listado: Mapped[int | None] = query_expression()
    total_listado: Mapped[int | None] = query_expression()

    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)

    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"), nullable=False)

    usuario: Mapped["Usuario"] = relationship("Usuario")
    categoria: Mapped["Categoria"] = relationship("Categoria")
    tags: Mapped[list["Tag"]] = relationship(
        "Tag", secondary=pregunta_tags, back_populates="preguntas"
    )
    respuestas: Mapped[list["Respuesta"]] = relationship(
        "Respuesta", back_populates="pregunta", cascade="all, delete-orphan"
    )
    adjuntos: Mapped[list["AdjuntoPregunta"]] = relationship(
        back_populates="pregunta", cascade="all, delete-orphan", order_by="AdjuntoPregunta.orden"
    )


class AdjuntoPregunta(db.Model):
    """Metadatos del archivo; su contenido se guarda fuera de la carpeta pública."""

    __tablename__ = "adjuntos_pregunta"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    pregunta_id: Mapped[int] = mapped_column(ForeignKey("preguntas.id"), index=True)
    nombre_original: Mapped[str] = mapped_column(String(120), nullable=False)
    tamanio: Mapped[int] = mapped_column(nullable=False)
    orden: Mapped[int] = mapped_column(nullable=False)
    pregunta: Mapped["Pregunta"] = relationship(back_populates="adjuntos")
