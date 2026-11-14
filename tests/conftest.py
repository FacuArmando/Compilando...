
import pytest

from compilando import create_app
from compilando.extensions import db
from compilando.modules.auth.models import Usuario


@pytest.fixture()
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
    })

    with app.app_context():
        db.create_all()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture()
def usuario(app):
    usuario = Usuario(
        username="usuario_test",
        email="usuario@test.com",
        password_hash="hash_de_prueba"
    )

    db.session.add(usuario)
    db.session.commit()

    return usuario
