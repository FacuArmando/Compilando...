from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from compilando.extensions import db

if TYPE_CHECKING:
    from compilando.modules.auth.models import Usuario
    from compilando.modules.questions.models import Pregunta

DIAS_SEMANA = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


class Respuesta(db.Model):
    """Representa una respuesta publicada por un usuario a una pregunta."""

    __tablename__ = "respuestas"

    id: Mapped[int] = mapped_column(primary_key=True)
    cuerpo: Mapped[str] = mapped_column(Text, nullable=False)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    pregunta_id: Mapped[int] = mapped_column(ForeignKey("preguntas.id"), nullable=False)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)

    pregunta: Mapped["Pregunta"] = relationship("Pregunta", back_populates="respuestas")
    usuario: Mapped["Usuario"] = relationship("Usuario")

    @property
    def fecha_formateada(self) -> str:
        """Devuelve la fecha en formato: 'lunes 16 de noviembre de 2026, a las 20:58 pm'."""
        dia_semana = DIAS_SEMANA[self.fecha.weekday()]
        mes = MESES[self.fecha.month - 1]
        sufijo = "am" if self.fecha.hour < 12 else "pm"
        hora = self.fecha.strftime("%H:%M")
        return f"{dia_semana} {self.fecha.day} de {mes} de {self.fecha.year}, a las {hora} {sufijo}"
