"""Archivos persistentes, atomicidad y cupo sin red ni proveedores externos."""

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import func, select, text
from werkzeug.datastructures import FileStorage

from compilando import create_app
from compilando.extensions import db
from compilando.modules.auth.models import Usuario
from compilando.modules.auth.services import cambiar_avatar, eliminar_avatar
from compilando.modules.questions.services import publicar_pregunta
from compilando.storage import Archivo, guardar_blob, leer_blob


@pytest.fixture
def persistent_app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "clave-solo-pruebas",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'archivos.sqlite'}",
            "STORAGE_BACKEND": "database",
        }
    )
    with app.app_context():
        db.create_all()
        db.session.execute(text("PRAGMA foreign_keys=ON"))
        user = Usuario(username="prueba", email="prueba@example.test", password_hash="prueba")
        db.session.add(user)
        db.session.commit()
        yield app, user
        db.session.remove()
        db.engine.dispose()


def image_file():
    buffer = BytesIO()
    Image.new("RGB", (600, 400), "blue").save(buffer, "PNG")
    buffer.seek(0)
    return FileStorage(buffer, filename="avatar.png")


def test_avatar_persiste_y_reemplazo_no_deja_huerfanos(persistent_app, monkeypatch):
    app, user = persistent_app
    monkeypatch.setattr(Path, "mkdir", lambda *a, **kw: pytest.fail("No escribir en disco"))
    cambiar_avatar(user, image_file())
    name = db.session.scalar(select(Usuario.avatar_filename).where(Usuario.id == user.id))
    db.session.remove()
    db.engine.dispose()
    client = app.test_client()
    assert client.get(f"/auth/avatar/{name}").status_code == 200
    assert client.get(f"/auth/avatar/{name}?size=thumb").status_code == 200
    user = db.session.get(Usuario, user.id)
    cambiar_avatar(user, image_file())
    assert client.get(f"/auth/avatar/{name}").status_code == 404
    assert db.session.scalar(select(func.count()).select_from(Archivo)) == 2
    eliminar_avatar(user)
    assert db.session.scalar(select(func.count()).select_from(Archivo)) == 0


def test_adjuntos_persisten_descarga_y_borrado_cascada(persistent_app, monkeypatch):
    app, user = persistent_app
    monkeypatch.setattr(Path, "mkdir", lambda *a, **kw: pytest.fail("No escribir en disco"))
    question = publicar_pregunta(
        "PROGRAMACIÓN con ÑANDÚ y C++",
        "Contenido de prueba.",
        "Python",
        [],
        user,
        archivos=[FileStorage(BytesIO(b"print('hola')"), filename="ejemplo.py")],
    )
    attachment = question.adjuntos[0]
    url = f"/questions/{question.id}/attachments/{attachment.id}"
    db.session.remove()
    db.engine.dispose()
    client = app.test_client()
    assert client.get(url).status_code == 200
    result = client.get(url + "/download")
    assert result.data == b"print('hola')"
    assert "attachment;" in result.headers["Content-Disposition"]
    from compilando.modules.questions.models import Pregunta

    db.session.execute(text("PRAGMA foreign_keys=ON"))
    db.session.delete(db.session.get(Pregunta, question.id))
    db.session.commit()
    assert db.session.scalar(select(func.count()).select_from(Archivo)) == 0


def test_fallo_commit_revierte_archivos_y_avatar(persistent_app, monkeypatch):
    _, user = persistent_app

    def fail():
        raise RuntimeError("Fallo simulado")

    monkeypatch.setattr(db.session, "commit", fail)
    with pytest.raises(RuntimeError, match="Fallo simulado"):
        cambiar_avatar(user, image_file())
    assert db.session.scalar(select(func.count()).select_from(Archivo)) == 0
    assert db.session.scalar(select(Usuario.avatar_filename)) is None


def test_cupo_y_rollback_no_dejan_datos(persistent_app):
    app, user = persistent_app
    app.config["STORAGE_TOTAL_BYTES"] = 5
    guardar_blob("avatars/primero.png", b"1234", usuario_id=user.id)
    with pytest.raises(ValueError, match="lleno"):
        guardar_blob("avatars/segundo.png", b"12", usuario_id=user.id)
    db.session.rollback()
    assert leer_blob("avatars/primero.png") is None


def test_rechaza_rutas_de_avatar_y_adjunto_de_otra_pregunta(persistent_app):
    app, _ = persistent_app
    client = app.test_client()
    assert client.get("/auth/avatar/..%5carchivo.png").status_code == 404
    assert client.get("/questions/1/attachments/inexistente/download").status_code == 404
