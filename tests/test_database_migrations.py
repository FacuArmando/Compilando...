"""El historial completo funciona con el runner transaccional y con SQLite."""

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from compilando import create_app
from compilando.extensions import db


def test_historial_completo_en_transaccion_externa(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "clave-solo-para-pruebas",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'migraciones.sqlite'}",
        }
    )
    with app.app_context():
        try:
            with db.engine.connect() as connection:
                # SQLite necesita BEGIN explícito para incluir DDL en el rollback.
                connection.exec_driver_sql("BEGIN")
                config = app.extensions["migrate"].migrate.get_config()
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
                assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                    "d9e5f6a712b3"
                )
                context = MigrationContext.configure(connection)
                assert compare_metadata(context, db.metadata) == []
                connection.rollback()
            # El env no debe confirmar por su cuenta la transacción del llamador.
            assert inspect(db.engine).get_table_names() == []
        finally:
            db.session.remove()
            db.engine.dispose()
