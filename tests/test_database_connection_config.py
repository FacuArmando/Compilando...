"""Regresión de la contraseña separada que causaba 500 con el perfil Supabase."""

import pytest
from sqlalchemy.pool import NullPool

from compilando import create_app
from compilando.extensions import db

URI = "postgresql://postgres.proyecto@pooler.example.invalid:5432/postgres"


def test_contrasena_separada_se_aplica_despues_de_overrides(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", URI)
    monkeypatch.setenv("DATABASE_PASSWORD", "valor-del-entorno")
    secret = "clave-con@:/#%y+simbolos"
    app = create_app({"TESTING": True, "DATABASE_PASSWORD": secret})
    with app.app_context():
        assert db.engine.url.password == secret
        assert db.engine.dialect.driver == "psycopg"
        assert secret not in str(db.engine.url)
        assert app.config["SQLALCHEMY_ENGINE_OPTIONS"]["connect_args"]["sslmode"] == "require"
        db.engine.dispose()


def test_override_sqlite_no_hereda_configuracion_postgres(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", URI)
    monkeypatch.setenv("DATABASE_PASSWORD", "clave-remota")
    monkeypatch.setenv("DATABASE_POOL_MODE", "transaction")
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        assert db.engine.dialect.name == "sqlite"
        assert not app.config["SQLALCHEMY_ENGINE_OPTIONS"].get("connect_args")
        db.engine.dispose()


def test_transaction_pooler_no_prepara_sentencias_ni_duplica_pool():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": URI,
            "DATABASE_PASSWORD": "prueba",
            "DATABASE_POOL_MODE": "transaction",
        }
    )
    with app.app_context():
        assert isinstance(db.engine.pool, NullPool)
        assert app.config["SQLALCHEMY_ENGINE_OPTIONS"]["connect_args"]["prepare_threshold"] is None
        db.engine.dispose()


@pytest.mark.parametrize("uri", [URI + "?sslmode=disable", "postgresql:///sin-host"])
def test_configuracion_invalida_no_expone_secretos(uri):
    with pytest.raises(RuntimeError) as error:
        create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": uri,
                "DATABASE_PASSWORD": "secreto-no-publicar",
            }
        )
    assert "secreto-no-publicar" not in str(error.value)
    assert error.value.__suppress_context__
