"""Una consulta compartida por pregunta; distingue solicitante y autor IA."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from compilando.extensions import db


class SolicitudIA(db.Model):
    __tablename__ = "solicitudes_ia"

    pregunta_id: Mapped[int] = mapped_column(ForeignKey("preguntas.id"), primary_key=True)
    solicitante_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    respuesta_id: Mapped[int | None] = mapped_column(ForeignKey("respuestas.id"), unique=True)
    token: Mapped[str] = mapped_column(String(32), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    vence: Mapped[datetime] = mapped_column(DateTime, nullable=False)
