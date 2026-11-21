from sqlalchemy.orm import Mapped, mapped_column

from compilando.extensions import db


class Categoria(db.Model):
    """Representa una categoría de preguntas."""

    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str]
    descripcion: Mapped[str]
