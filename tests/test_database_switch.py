"""Elegir motor sin mover datos, perder perfiles ni abrir conexiones no solicitadas."""

import pytest

from compilando import create_app
from compilando.extensions import db

REMOTE = "postgresql://postgres.prueba@pooler.example.invalid:5432/postgres"


def test_sqlite_ignora_uri_remota_y_no_lee_el_perfil(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", REMOTE)
    monkeypatch.setenv("DATABASE_PASSWORD", "secreto-remoto")

    def unexpected(*args, **kwargs):
        pytest.fail("SQLite no debe leer perfiles ni conectar a PostgreSQL")

    monkeypatch.setattr("compilando.database.dotenv_values", unexpected)
    monkeypatch.setattr("psycopg.connect", unexpected)
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_BACKEND": "sqlite",
            "SQLITE_DATABASE_URL": f"sqlite:///{tmp_path / 'local.sqlite'}",
        }
    )
    with app.app_context():
        assert db.engine.dialect.name == "sqlite"
        assert app.config["DATABASE_PASSWORD"] == ""
        assert app.config["DATABASE_BACKEND_ACTIVE"] == "sqlite"
        db.engine.dispose()


def test_supabase_lee_perfil_privado_sin_exportar_variables(monkeypatch, tmp_path):
    profile = tmp_path / ".env.supabase.local"
    profile.write_text(
        f"DATABASE_URL='{REMOTE}'\nDATABASE_PASSWORD='clave@${{LITERAL}}#%'\n"
        "DATABASE_POOL_MODE=transaction\n"
    )
    monkeypatch.setenv("DATABASE_PASSWORD", "otra-clave")
    monkeypatch.setenv("LITERAL", "no-interpolar")
    original = profile.read_bytes()
    app = create_app(
        {"TESTING": True, "DATABASE_BACKEND": "supabase", "SUPABASE_ENV_FILE": str(profile)}
    )
    with app.app_context():
        assert db.engine.url.password == "clave@${LITERAL}#%"
        assert app.config["DATABASE_POOL_MODE"] == "transaction"
        assert app.config["DATABASE_BACKEND_ACTIVE"] == "postgresql"
        db.engine.dispose()
    import os

    assert os.environ["DATABASE_PASSWORD"] == "otra-clave"
    assert profile.read_bytes() == original


def test_variables_supabase_no_mezclan_password_de_otro_perfil(tmp_path):
    profile = tmp_path / ".env.supabase.local"
    profile.write_text(f"DATABASE_URL='{REMOTE}'\nDATABASE_PASSWORD='clave-otro-proyecto'\n")
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_BACKEND": "supabase",
            "SUPABASE_ENV_FILE": str(profile),
            "SUPABASE_DATABASE_URL": REMOTE,
            "SUPABASE_DATABASE_PASSWORD": "clave-del-proyecto-seleccionado",
        }
    )
    with app.app_context():
        assert db.engine.url.password == "clave-del-proyecto-seleccionado"
        db.engine.dispose()


def test_supabase_sin_perfil_falla_sin_volver_a_sqlite(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="Elegiste Supabase"):
        create_app(
            {
                "TESTING": True,
                "DATABASE_BACKEND": "supabase",
                "SUPABASE_ENV_FILE": str(tmp_path / "inexistente"),
            }
        )
    assert not list(tmp_path.iterdir())


def test_supabase_admite_configuracion_legacy(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", REMOTE)
    monkeypatch.setenv("DATABASE_PASSWORD", "clave-compatible")
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_BACKEND": "supabase",
            "SUPABASE_ENV_FILE": str(tmp_path / "inexistente"),
        }
    )
    with app.app_context():
        assert db.engine.url.password == "clave-compatible"
        db.engine.dispose()


def test_uri_de_pruebas_prevalece_sobre_selector_y_perfil_incompleto(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_BACKEND": "supabase",
            "SUPABASE_ENV_FILE": str(tmp_path / "inexistente"),
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    with app.app_context():
        assert db.engine.dialect.name == "sqlite"
        db.engine.dispose()


@pytest.mark.parametrize("mode", ["supa", "sqlitee", "postgres"])
def test_selector_invalido_no_elige_otra_base(mode):
    with pytest.raises(RuntimeError, match="DATABASE_BACKEND"):
        create_app({"TESTING": True, "DATABASE_BACKEND": mode})


def test_info_no_conecta_ni_imprime_password(monkeypatch, tmp_path):
    def unexpected(*args, **kwargs):
        pytest.fail("database-info no debe abrir conexiones")

    monkeypatch.setattr("psycopg.connect", unexpected)
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_BACKEND": "supabase",
            "SUPABASE_DATABASE_URL": REMOTE,
            "SUPABASE_DATABASE_PASSWORD": "no-mostrar",
            "SUPABASE_ENV_FILE": str(tmp_path / "inexistente"),
        }
    )
    result = app.test_cli_runner().invoke(args=["database-info"])
    assert result.exit_code == 0
    assert "PostgreSQL / Supabase" in result.output
    assert "no-mostrar" not in result.output and "example.invalid" not in result.output


def test_check_fallido_no_expone_credenciales(monkeypatch):
    from sqlalchemy.exc import OperationalError

    app = create_app(
        {
            "TESTING": True,
            "DATABASE_BACKEND": "supabase",
            "SUPABASE_DATABASE_URL": REMOTE,
            "SUPABASE_DATABASE_PASSWORD": "no-mostrar",
        }
    )

    def fail(*args, **kwargs):
        raise OperationalError("no-mostrar", None, Exception("detalles-privados"))

    monkeypatch.setattr(db.session, "execute", fail)
    result = app.test_cli_runner().invoke(args=["check-db"])
    assert result.exit_code != 0
    assert "No se pudo conectar" in result.output
    assert "no-mostrar" not in result.output and "detalles-privados" not in result.output


def test_cambiar_y_volver_conserva_el_archivo_sqlite(tmp_path):
    path = tmp_path / "local.sqlite"
    config = {
        "TESTING": True,
        "DATABASE_BACKEND": "sqlite",
        "SQLITE_DATABASE_URL": f"sqlite:///{path}",
    }
    app = create_app(config)
    from sqlalchemy import text

    with app.app_context():
        db.session.execute(text("CREATE TABLE marcador (valor TEXT)"))
        db.session.execute(text("INSERT INTO marcador VALUES ('local')"))
        db.session.commit()
        db.engine.dispose()
    original = path.read_bytes()
    remote = create_app(
        {
            "TESTING": True,
            "DATABASE_BACKEND": "supabase",
            "SUPABASE_DATABASE_URL": REMOTE,
            "SUPABASE_DATABASE_PASSWORD": "prueba",
        }
    )
    with remote.app_context():
        assert db.engine.dialect.name == "postgresql"
        db.engine.dispose()
    assert path.read_bytes() == original
    local = create_app(config)
    with local.app_context():
        assert db.session.scalar(text("SELECT valor FROM marcador")) == "local"
        db.session.remove()
        db.engine.dispose()
