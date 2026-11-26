"""Configurar PostgreSQL después de aplicar los overrides de cada aplicación."""

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.pool import NullPool


def configure_database(app) -> str:
    """Elegir Psycopg 3 y conexiones TLS sin alterar la configuración de SQLite."""
    try:
        url = make_url(app.config["SQLALCHEMY_DATABASE_URI"])
        if url.drivername in {"postgres", "postgresql"}:
            url = url.set(drivername="postgresql+psycopg")
        backend = url.get_backend_name()
        if backend == "sqlite":
            if app.config["APP_ENV"] == "production" and not app.testing:
                raise RuntimeError("Producción requiere DATABASE_URL de PostgreSQL.")
            return backend
        if backend != "postgresql" or url.drivername != "postgresql+psycopg":
            raise ValueError
        mode = app.config.get("DATABASE_POOL_MODE", "direct")
        if mode not in {"direct", "session", "transaction"}:
            raise ValueError
        if url.query.get("sslmode", "require") not in {"require", "verify-ca", "verify-full"}:
            raise ValueError
        password = app.config.get("DATABASE_PASSWORD")
        if password:
            url = url.set(password=password)
        if not url.host or not url.database or not url.username:
            raise ValueError
    except (ArgumentError, KeyError, TypeError, ValueError):
        # No incluir la URL ni la excepción original: pueden contener credenciales.
        raise RuntimeError(
            "Configuración de base inválida. Usá SQLite o PostgreSQL con Psycopg 3, "
            "TLS y DATABASE_POOL_MODE=direct, session o transaction."
        ) from None

    options = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS") or {})
    options.setdefault("pool_pre_ping", True)
    connect_args = dict(options.get("connect_args") or {})
    connect_args.setdefault("connect_timeout", 10)
    connect_args.setdefault("sslmode", url.query.get("sslmode", "require"))
    if connect_args["sslmode"] not in {"require", "verify-ca", "verify-full"}:
        raise RuntimeError("PostgreSQL requiere una conexión TLS.")
    if mode == "transaction":
        # El pooler ya administra conexiones. No mantener otro pool por instancia.
        for key in ("pool_size", "max_overflow", "pool_timeout", "pool_recycle", "pool_use_lifo"):
            options.pop(key, None)
        options["poolclass"] = NullPool
        connect_args["prepare_threshold"] = None
    else:
        options.setdefault("pool_size", 2)
        options.setdefault("max_overflow", 0)
        options.setdefault("pool_timeout", 10)
    options["connect_args"] = connect_args
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = options
    # URL conserva caracteres especiales de la contraseña y oculta esta en su repr.
    app.config["SQLALCHEMY_DATABASE_URI"] = url
    return backend
