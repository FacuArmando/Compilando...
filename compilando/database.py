"""Preparar la conexión final después de aplicar overrides de cada aplicación."""

from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.pool import NullPool


def _select_profile(app):
    mode = app.config.get("DATABASE_BACKEND", "auto").strip().lower()
    if mode not in {"auto", "sqlite", "supabase"}:
        raise RuntimeError("DATABASE_BACKEND debe ser sqlite, supabase o auto.")
    if mode == "sqlite":
        app.config["SQLALCHEMY_DATABASE_URI"] = app.config["SQLITE_DATABASE_URL"]
        app.config["DATABASE_PASSWORD"] = ""
    elif mode == "supabase":
        if app.config.get("SUPABASE_DATABASE_URL"):
            url = app.config["SUPABASE_DATABASE_URL"]
            password = app.config.get("SUPABASE_DATABASE_PASSWORD", "")
            pool_mode = app.config["SUPABASE_DATABASE_POOL_MODE"]
        else:
            # Leer el perfil sin exportarlo al entorno ni interpolar su contraseña.
            path = Path(app.config["SUPABASE_ENV_FILE"])
            profile = dotenv_values(path, interpolate=False) if path.is_file() else {}
            if profile.get("DATABASE_URL"):
                url = profile["DATABASE_URL"]
                password = profile.get("DATABASE_PASSWORD") or ""
                pool_mode = profile.get("DATABASE_POOL_MODE") or "session"
            else:
                # Compatibilidad con .env o despliegues que ya usaban DATABASE_URL.
                url = app.config["SQLALCHEMY_DATABASE_URI"]
                password = app.config.get("DATABASE_PASSWORD", "")
                pool_mode = app.config["DATABASE_POOL_MODE"]
        app.config.update(
            SQLALCHEMY_DATABASE_URI=url, DATABASE_PASSWORD=password, DATABASE_POOL_MODE=pool_mode
        )
    return mode


def configure_database(app, *, explicit_uri=False):
    # Un URI explícito de create_app(test_config) conserva el aislamiento de pruebas.
    mode = "auto" if explicit_uri else _select_profile(app)
    try:
        url = make_url(app.config["SQLALCHEMY_DATABASE_URI"])
        backend = url.get_backend_name()
        if mode == "supabase" and backend != "postgresql":
            raise RuntimeError(
                "Elegiste Supabase pero falta su conexión PostgreSQL. "
                "Completá .env.supabase.local o SUPABASE_DATABASE_URL y su contraseña."
            )
        if mode == "sqlite" and backend != "sqlite":
            raise RuntimeError("SQLITE_DATABASE_URL debe apuntar a SQLite.")
        app.config["DATABASE_BACKEND_ACTIVE"] = backend
        if backend == "sqlite":
            return backend
        if backend != "postgresql":
            raise ValueError
        mode = app.config.get("DATABASE_POOL_MODE", "session")
        if mode not in {"direct", "session", "transaction"}:
            raise ValueError
        url = url.set(drivername="postgresql+psycopg")
        if app.config.get("DATABASE_PASSWORD"):
            url = url.set(password=app.config["DATABASE_PASSWORD"])
        if not url.host or not url.database or not url.username:
            raise ValueError
        sslmode = url.query.get("sslmode", "require")
        if sslmode not in {"require", "verify-ca", "verify-full"}:
            raise ValueError
    except (ArgumentError, KeyError, TypeError, ValueError):
        raise RuntimeError(
            "Revisá la configuración PostgreSQL: conexión, TLS y modo de pool. "
            "No compartas credenciales."
        ) from None

    options = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS") or {})
    connect_args = dict(options.get("connect_args") or {})
    connect_args.setdefault("connect_timeout", 10)
    connect_args.setdefault("sslmode", sslmode)
    if connect_args["sslmode"] not in {"require", "verify-ca", "verify-full"}:
        raise RuntimeError("PostgreSQL requiere TLS.")
    options.setdefault("pool_pre_ping", True)
    if mode == "transaction":
        for name in ("pool_size", "max_overflow", "pool_timeout", "pool_recycle", "pool_use_lifo"):
            options.pop(name, None)
        options["poolclass"] = NullPool
        connect_args["prepare_threshold"] = None
    else:
        options.setdefault("pool_size", 2)
        options.setdefault("max_overflow", 0)
        options.setdefault("pool_timeout", 10)
    options["connect_args"] = connect_args
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = options
    # URL maneja caracteres especiales sin concatenar la contraseña en una cadena.
    app.config["SQLALCHEMY_DATABASE_URI"] = url
    return backend
