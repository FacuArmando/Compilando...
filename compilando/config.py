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
        "ADMIN_ACTIVATION_CODE": os.environ.get("ADMIN_ACTIVATION_CODE", ""),
        "SQLALCHEMY_DATABASE_URI": os.environ.get("DATABASE_URL")
        or f"sqlite:///{database_path.as_posix()}",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "QUESTION_UPLOAD_FOLDER": str(database_path.parent / "question-attachments"),
        "QUESTION_ATTACHMENT_MAX_FILES": 10,
        "QUESTION_ATTACHMENT_MAX_BYTES": 1024 * 1024,
        "QUESTION_ATTACHMENT_TOTAL_BYTES": 5 * 1024 * 1024,
        "QUESTION_ATTACHMENT_EXTENSIONS": (".java", ".py", ".js", ".jsx", ".txt"),
        "AVATAR_UPLOAD_FOLDER": str(database_path.parent / "avatars"),
        "AVATAR_MAX_BYTES": 20 * 1024 * 1024,
        "MAX_CONTENT_LENGTH": 21 * 1024 * 1024,
        "AVATAR_MAX_PIXELS": 40_000_000,
        "AVATAR_THUMB_SIZE": 256,
        "AVATAR_FULL_SIZE": 1280,
        "AVATAR_EXTENSIONS": (".jpg", ".jpeg", ".png", ".webp"),
        "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", ""),
        "GEMINI_MODEL": "gemini-3.5-flash-lite",
        "AI_TIMEOUT_SECONDS": 40,
        "AI_MAX_CONTEXT_BYTES": 48 * 1024,
        "AI_MAX_OUTPUT_TOKENS": 1800,
        "AI_REQUEST_LIFETIME": timedelta(seconds=90),
        "AI_ACCOUNT_LIMIT": 5,
        "AI_IP_LIMIT": 20,
        "AI_GLOBAL_LIMIT": 30,
        "AI_TRIGGER_TAGS": ("ia", "ai", "gemini", "asistente-ia"),
        "AI_AUTO_RESPOND_UNANSWERED": True, 
        "AI_UNANSWERED_MINUTES": int(os.environ.get("AI_UNANSWERED_MINUTES", 1440)),
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
        "ADMIN_ACTIVATION_IP_LIMIT": 5,
        "ADMIN_ACTIVATION_ACCOUNT_LIMIT": 5,
        "AUTH_PASSWORD_IP_LIMIT": 30,
        "AUTH_PASSWORD_ACCOUNT_LIMIT": 5,
        "TRUSTED_HOSTS": [host.strip() for host in trusted_hosts.split(",") if host.strip()]
        or None,
    }
