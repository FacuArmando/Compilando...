"""Preparación de PostgreSQL sin conexiones remotas ni cambios en bases reales."""

from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool

from compilando import create_app
from compilando.extensions import db

URI = "postgresql://postgres.proyecto:placeholder@pooler.example.invalid:5432/postgres"


def postgres_app(monkeypatch, **overrides):
    monkeypatch.setenv("APP_ENV", "development")
    return create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": URI,
            "DATABASE_PASSWORD": "",
            "DATABASE_POOL_MODE": "session",
            **overrides,
        }
    )


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+psycopg"])
def test_aliases_usan_psycopg3_y_clave_separada_sin_escapes(monkeypatch, scheme):
    secret = "clave@con:/#%y+simbolos"
    app = postgres_app(
        monkeypatch,
        SQLALCHEMY_DATABASE_URI=URI.replace("postgresql:", scheme + ":"),
        DATABASE_PASSWORD=secret,
    )
    with app.app_context():
        assert db.engine.dialect.name == "postgresql"
        assert db.engine.dialect.driver == "psycopg"
        assert db.engine.url.password == secret
        assert secret not in str(db.engine.url)
        assert app.config["SQLALCHEMY_ENGINE_OPTIONS"]["connect_args"] == {
            "sslmode": "require",
            "connect_timeout": 10,
        }
        db.engine.dispose()


def test_transaction_pooler_no_duplica_pool_ni_prepara_sentencias(monkeypatch):
    app = postgres_app(
        monkeypatch,
        DATABASE_POOL_MODE="transaction",
        SQLALCHEMY_ENGINE_OPTIONS={"pool_size": 5, "max_overflow": 10},
    )
    with app.app_context():
        assert isinstance(db.engine.pool, NullPool)
        args = app.config["SQLALCHEMY_ENGINE_OPTIONS"]["connect_args"]
        assert args["prepare_threshold"] is None
        assert args["sslmode"] == "require"
        db.engine.dispose()


@pytest.mark.parametrize("mode", ["session", "direct"])
def test_sesion_y_directa_conservan_opciones_propias(monkeypatch, mode):
    app = postgres_app(
        monkeypatch,
        DATABASE_POOL_MODE=mode,
        SQLALCHEMY_DATABASE_URI=URI + "?sslmode=verify-full",
        SQLALCHEMY_ENGINE_OPTIONS={"pool_size": 2},
    )
    with app.app_context():
        assert not isinstance(db.engine.pool, NullPool)
        assert db.engine.pool.size() == 2
        assert app.config["SQLALCHEMY_ENGINE_OPTIONS"]["connect_args"]["sslmode"] == "verify-full"
        db.engine.dispose()


@pytest.mark.parametrize(
    "config",
    [
        {"SQLALCHEMY_DATABASE_URI": "mysql://user:secreto-no-publicar@host/db"},
        {"SQLALCHEMY_DATABASE_URI": "postgresql+psycopg2://user:secreto-no-publicar@host/db"},
        {"SQLALCHEMY_DATABASE_URI": "postgresql://user:secreto-no-publicar@host:no-es-puerto/db"},
        {"SQLALCHEMY_DATABASE_URI": URI + "?sslmode=disable"},
        {"SQLALCHEMY_DATABASE_URI": "postgresql:///sin-host"},
        {"DATABASE_POOL_MODE": "incorrecto"},
    ],
)
def test_configuracion_invalida_no_filtra_la_url(monkeypatch, config):
    with pytest.raises(RuntimeError) as error:
        postgres_app(monkeypatch, **config)
    assert "secreto-no-publicar" not in str(error.value)
    assert "example.invalid" not in str(error.value)
    assert error.value.__suppress_context__


def test_no_se_puede_desactivar_tls_con_connect_args(monkeypatch):
    with pytest.raises(RuntimeError, match="TLS"):
        postgres_app(
            monkeypatch, SQLALCHEMY_ENGINE_OPTIONS={"connect_args": {"sslmode": "disable"}}
        )


def test_override_sqlite_no_hereda_opciones_de_postgres(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", URI)
    monkeypatch.setenv("DATABASE_PASSWORD", "secreto-remoto")
    monkeypatch.setenv("DATABASE_POOL_MODE", "transaction")
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        assert db.engine.dialect.name == "sqlite"
        assert not app.config["SQLALCHEMY_ENGINE_OPTIONS"].get("connect_args")
        db.engine.dispose()


def test_crear_app_postgres_no_crea_carpetas_ni_abre_conexion(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("El arranque no debe escribir ni abrir la conexión")

    monkeypatch.setattr(Path, "mkdir", unexpected)
    monkeypatch.setattr("psycopg.connect", unexpected)
    app = postgres_app(monkeypatch)
    with app.app_context():
        assert db.engine.dialect.name == "postgresql"
        db.engine.dispose()


def test_check_postgres_rechaza_fallback_sqlite():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    result = app.test_cli_runner().invoke(args=["check-postgres"])
    assert result.exit_code != 0
    assert "No hay una conexión PostgreSQL" in result.output
    assert "PostgreSQL: OK" not in result.output


def test_check_postgres_solo_hace_select_y_no_imprime_credenciales(monkeypatch):
    app = postgres_app(monkeypatch, DATABASE_PASSWORD="secreto-no-publicar")
    calls = []
    monkeypatch.setattr(db.session, "execute", lambda statement: calls.append(str(statement)))
    result = app.test_cli_runner().invoke(args=["check-postgres"])
    assert result.exit_code == 0 and calls == ["SELECT 1"]
    assert "Conexión PostgreSQL: OK" in result.output
    assert "secreto-no-publicar" not in result.output
    assert "pooler.example.invalid" not in result.output


def test_check_postgres_no_muestra_detalles_privados_en_error(monkeypatch):
    app = postgres_app(monkeypatch)

    def fail(*args):
        raise OperationalError("secreto-no-publicar", None, Exception("credenciales privadas"))

    monkeypatch.setattr(db.session, "execute", fail)
    result = app.test_cli_runner().invoke(args=["check-postgres"])
    assert result.exit_code != 0
    assert "No se pudo conectar a PostgreSQL" in result.output
    assert "secreto-no-publicar" not in result.output
    assert "credenciales privadas" not in result.output
