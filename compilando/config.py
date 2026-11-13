"""Centraliza la configuración de la aplicación.

Lee la clave secreta y la dirección de la base de datos del entorno; si no hay
una dirección definida, usa SQLite. También configura las cookies de sesión.
"""

import os
from datetime import timedelta
from pathlib import Path


def load_config() -> dict:
    database_path = Path(__file__).resolve().parents[1] / "instance" / "compilando.sqlite"
    environment = os.environ.get("APP_ENV", "development")
    if environment not in {"development", "production"}:
        raise RuntimeError("APP_ENV debe ser development o production.")
    production = environment == "production"
    trusted_hosts = os.environ.get("TRUSTED_HOSTS", "")
    return {
        "APP_ENV": "production" if production else "development",
        "SECRET_KEY": os.environ.get("SECRET_KEY"),
        "SQLALCHEMY_DATABASE_URI": os.environ.get("DATABASE_URL")
        or f"sqlite:///{database_path.as_posix()}",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": production,
        "SESSION_COOKIE_NAME": "__Host-compilando" if production else "compilando_session",
        "SESSION_COOKIE_PATH": "/",
        "SESSION_REFRESH_EACH_REQUEST": False,
        "PERMANENT_SESSION_LIFETIME": timedelta(hours=8),
        "AUTH_SESSION_LIFETIME": timedelta(hours=8),
        "AUTH_IDLE_TIMEOUT": timedelta(minutes=30),
        "AUTH_RATE_WINDOW": timedelta(minutes=15),
        "AUTH_LOGIN_EMAIL_LIMIT": 5,
        "AUTH_LOGIN_IP_LIMIT": 30,
        "AUTH_REGISTER_IP_LIMIT": 10,
        "TRUSTED_HOSTS": [host.strip() for host in trusted_hosts.split(",") if host.strip()]
        or None,
    }
