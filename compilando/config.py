"""Centraliza la configuración de la aplicación.

Lee la clave secreta y la dirección de la base de datos del entorno; si no hay
una dirección definida, usa SQLite. También configura las cookies de sesión.
"""

import os
from pathlib import Path


def load_config() -> dict:
    database_path = Path(__file__).resolve().parents[1] / "instance" / "compilando.sqlite"
    return {
        "SECRET_KEY": os.environ.get("SECRET_KEY"),
        "SQLALCHEMY_DATABASE_URI": os.environ.get("DATABASE_URL")
        or f"sqlite:///{database_path.as_posix()}",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
    }
