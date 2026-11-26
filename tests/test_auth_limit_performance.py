"""Contadores atómicos sin savepoints ni limpieza global en cada intento."""

from contextlib import contextmanager
from datetime import timedelta

import pytest
from sqlalchemy import event, select, update

from compilando.extensions import db
from compilando.modules.auth.models import LimiteIntentos
from compilando.modules.auth.security import DemasiadosIntentos, limitar_intentos
from compilando.modules.auth.sessions import ahora_utc


@contextmanager
def operations():
    verbs = []

    def record(conn, cursor, sql, params, context, many):
        verbs.append(sql.lstrip().split(None, 1)[0].upper())

    engine = db.engine
    event.listen(engine, "before_cursor_execute", record)
    try:
        yield verbs
    finally:
        event.remove(engine, "before_cursor_execute", record)


def test_intentos_nuevos_y_repetidos_sin_savepoints(app):
    with app.test_request_context():
        with operations() as first:
            limitar_intentos("login", "prueba@example.test")
        with operations() as again:
            limitar_intentos("login", "prueba@example.test")
    assert first.count("INSERT") == 2 and first.count("DELETE") == 2
    assert again == ["INSERT", "INSERT"]
    assert "SAVEPOINT" not in first
    assert list(db.session.scalars(select(LimiteIntentos.intentos))) == [2, 2]


def test_ventana_se_reinicia_aunque_no_corresponda_limpiar(app):
    app.config["AUTH_LOGIN_EMAIL_LIMIT"] = 1
    with app.test_request_context():
        limitar_intentos("login", "prueba@example.test")
        with pytest.raises(DemasiadosIntentos):
            limitar_intentos("login", "prueba@example.test")
        db.session.execute(
            update(LimiteIntentos).values(inicio_ventana=ahora_utc() - timedelta(minutes=16))
        )
        db.session.commit()
        with operations() as reset:
            limitar_intentos("login", "prueba@example.test")
    assert reset == ["INSERT", "INSERT"]
    assert list(db.session.scalars(select(LimiteIntentos.intentos))) == [1, 1]


def test_limpieza_fallida_no_se_da_por_completada(app, monkeypatch):
    original = db.session.commit

    def fail():
        raise RuntimeError("Fallo simulado")

    monkeypatch.setattr(db.session, "commit", fail)
    with app.test_request_context():
        with pytest.raises(RuntimeError, match="Fallo simulado"):
            limitar_intentos("login", "prueba@example.test")
        assert "auth_cleanup_after" not in app.extensions
        monkeypatch.setattr(db.session, "commit", original)
        with operations() as retry:
            limitar_intentos("login", "prueba@example.test")
    assert retry.count("DELETE") == 2
