"""Normalización de búsquedas para SQLite, sin reescribir contenido almacenado."""

import unicodedata

from sqlalchemy import event

from compilando.extensions import db


def normalizar_busqueda(valor: str | None) -> str:
    """Ignorar acentos y mayúsculas; conservar ñ y símbolos de tecnologías."""
    texto = unicodedata.normalize("NFC", (valor or "").casefold())
    return "".join(
        caracter
        if caracter == "ñ"
        else "".join(
            parte
            for parte in unicodedata.normalize("NFD", caracter)
            if unicodedata.category(parte) != "Mn"
        )
        for caracter in texto
    )


def init_app(app):
    """Registrar la función en cada conexión del motor SQLite de esta aplicación."""
    with app.app_context():
        engine = db.engine
        if engine.dialect.name != "sqlite":
            return

        @event.listens_for(engine, "connect")
        def registrar(conexion, _):
            conexion.create_function(
                "normalizar_busqueda", 1, normalizar_busqueda, deterministic=True
            )
