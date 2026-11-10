"""Comprobar que las pruebas no comparten base de datos entre aplicaciones."""

from sqlalchemy import text

from compilando import create_app
from compilando.extensions import db


def test_applications_have_independent_databases():
    config = {"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"}
    first = create_app(config)
    second = create_app(config)

    with first.app_context():
        db.session.execute(text("CREATE TABLE isolation_probe (id INTEGER PRIMARY KEY)"))
        db.session.commit()

    with second.app_context():
        count = db.session.execute(
            text("SELECT COUNT(*) FROM sqlite_master WHERE name = 'isolation_probe'")
        ).scalar_one()
        assert count == 0

    with first.app_context():
        count = db.session.execute(
            text("SELECT COUNT(*) FROM sqlite_master WHERE name = 'isolation_probe'")
        ).scalar_one()
        assert count == 1
