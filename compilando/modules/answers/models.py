import re
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from compilando.extensions import db

if TYPE_CHECKING:
    from compilando.modules.auth.models import Usuario
    from compilando.modules.questions.models import Pregunta

DIAS_SEMANA = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


class EstadoRespuesta(Enum):
    """Estados posibles de aceptación de una respuesta."""

    NO_ACEPTADA = "No aceptada"
    ACEPTADA = "Aceptada"


def _formatear_fecha_es(dt: datetime) -> str:
    """Devuelve una fecha en formato: 'lunes 16 de noviembre de 2026, a las 20:58 pm'."""
    dia_semana = DIAS_SEMANA[dt.weekday()]
    mes = MESES[dt.month - 1]
    sufijo = "am" if dt.hour < 12 else "pm"
    hora = dt.strftime("%H:%M")
    return f"{dia_semana} {dt.day} de {mes} de {dt.year}, a las {hora} {sufijo}"


class Respuesta(db.Model):
    """Representa una respuesta publicada por un usuario o por IA a una pregunta."""

    __tablename__ = "respuestas"

    id: Mapped[int] = mapped_column(primary_key=True)
    cuerpo: Mapped[str] = mapped_column(Text, nullable=False)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    fecha_edicion: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    es_ia: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    modelo_ia: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    proveedor_ia: Mapped[str | None] = mapped_column(String(32), nullable=True, default=None)

    estado: Mapped[str] = mapped_column(
        String(20),
        default=EstadoRespuesta.NO_ACEPTADA.value,
        server_default=EstadoRespuesta.NO_ACEPTADA.value,
        nullable=False,
    )

    pregunta_id: Mapped[int] = mapped_column(ForeignKey("preguntas.id"), nullable=False)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)

    pregunta: Mapped["Pregunta"] = relationship("Pregunta", back_populates="respuestas")
    usuario: Mapped["Usuario | None"] = relationship("Usuario")

    @property
    def autor_nombre(self) -> str:
        """Identifica el nombre visible del autor según sea respuesta humana o de IA."""
        if self.es_ia:
            return self.modelo_ia or "Asistente IA"
        return self.usuario.username

    @property
    def autor_avatar(self) -> str | None:
        """Devuelve el nombre de archivo de la foto de perfil del autor si tiene."""
        if self.es_ia or self.usuario is None:
            return None
        return self.usuario.avatar_filename

    @property
    def es_autor_pregunta(self) -> bool:
        """Indica si quien respondió es el mismo usuario que publicó la pregunta."""
        return not self.es_ia and self.usuario_id == self.pregunta.usuario_id

    @property
    def bloques_ia(self) -> list[tuple[str, str]]:
        """Separar texto y código sin interpretar HTML del proveedor."""
        bloques = []
        for posicion, texto in enumerate(self.cuerpo.split("```")):
            if posicion % 2:
                lenguaje, salto, codigo = texto.partition("\n")
                if salto and re.fullmatch(r"[\w+#.\-]{0,24}", lenguaje.strip()):
                    texto = codigo
                bloques.append(("codigo", texto.strip("\n")))
            elif texto.strip():
                bloques.append(("texto", texto.strip()))
        return bloques

    @property
    def fecha_formateada(self) -> str:
        return _formatear_fecha_es(self.fecha)

    @property
    def fecha_edicion_formateada(self) -> str | None:
        if self.fecha_edicion is None:
            return None
        return _formatear_fecha_es(self.fecha_edicion)
