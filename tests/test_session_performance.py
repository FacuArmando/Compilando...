"""Costo común de navegar con sesión y controles que deben seguir siendo seguros."""

from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from flask import g, session
from sqlalchemy import event, select, update

from compilando import create_app
from compilando.extensions import db
from compilando.modules.auth import sessions
from compilando.modules.auth.models import Sesion, Usuario


@pytest.fixture
def navigation(tmp_path, monkeypatch):
    clock = [datetime(2026, 11, 26, 18)]
    monkeypatch.setattr(sessions, "ahora_utc", lambda: clock[0])
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "clave-solo-para-pruebas-de-navegacion",
            "APP_ENV": "development",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'navegacion.sqlite'}",
        }
    )

    @app.get("/_test/identity")
    def identity():
        user = g.usuario_actual
        if user is None:
            return {"authenticated": False}
        return {
            "authenticated": True,
            "name": user.username,
            "email": user.email,
            "avatar": user.avatar_filename,
            "admin": user.es_admin,
        }

    with app.app_context():
        db.create_all()
        user = Usuario(username="Mati", email="mati@example.test", password_hash="prueba")
        db.session.add(user)
        db.session.commit()
        with app.test_request_context():
            sessions.iniciar_sesion(user)
            token = session["auth_token"]
        engine = db.engine
    client = app.test_client()
    with client.session_transaction() as state:
        state["auth_token"] = token
    yield app, client, clock, engine
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


@contextmanager
def database_work(engine):
    work = {"sql": [], "commits": 0}

    def statement(conn, cursor, sql, parameters, context, many):
        # Solo verbos: no capturar datos, cookies ni parámetros.
        work["sql"].append(sql.lstrip().split(None, 1)[0].upper())

    def commit(conn):
        work["commits"] += 1

    event.listen(engine, "before_cursor_execute", statement)
    event.listen(engine, "commit", commit)
    try:
        yield work
    finally:
        event.remove(engine, "before_cursor_execute", statement)
        event.remove(engine, "commit", commit)


def test_navegacion_reciente_una_lectura_y_sin_escrituras(navigation):
    _, client, clock, engine = navigation
    clock[0] += timedelta(seconds=1)
    for _ in range(3):
        with database_work(engine) as work:
            response = client.get("/_test/identity")
        assert response.json["authenticated"] is True
        assert response.json["name"] == "Mati"
        assert response.json["avatar"] is None
        assert work == {"sql": ["SELECT"], "commits": 0}


def test_catalogo_con_cookie_no_consulta_sesion_y_respeta_etag(navigation):
    _, client, _, engine = navigation
    with database_work(engine) as work:
        response = client.get("/interface-catalog.js")
    assert response.status_code == 200
    assert work == {"sql": [], "commits": 0}
    assert response.headers["Cache-Control"] == "public, max-age=3600"
    assert "Set-Cookie" not in response.headers
    assert "Cookie" not in response.headers.get("Vary", "")
    with database_work(engine) as work:
        cached = client.get(
            "/interface-catalog.js", headers={"If-None-Match": response.headers["ETag"]}
        )
    assert cached.status_code == 304 and cached.data == b""
    assert work == {"sql": [], "commits": 0}


def test_actividad_se_registra_al_cumplir_intervalo_y_no_en_cada_click(navigation):
    app, client, clock, engine = navigation
    initial = clock[0]
    clock[0] += timedelta(seconds=29)
    assert client.get("/_test/identity").json["authenticated"]
    with app.app_context():
        assert db.session.scalar(select(Sesion.ultimo_acceso)) == initial
    clock[0] += timedelta(seconds=1)
    with database_work(engine) as work:
        assert client.get("/_test/identity").json["authenticated"]
    assert work == {"sql": ["SELECT", "UPDATE"], "commits": 1}
    with app.app_context():
        assert db.session.scalar(select(Sesion.ultimo_acceso)) == clock[0]
    with database_work(engine) as work:
        assert client.get("/_test/identity").json["authenticated"]
    assert work == {"sql": ["SELECT"], "commits": 0}


@pytest.mark.parametrize("reason", ["revoked", "expired", "idle", "permissions"])
def test_cambios_de_seguridad_se_observan_aunque_actividad_sea_reciente(navigation, reason):
    app, client, clock, _ = navigation
    assert client.get("/_test/identity").json["authenticated"]
    with app.app_context():
        if reason == "permissions":
            db.session.execute(update(Usuario).values(es_admin=True))
        else:
            values = (
                {"activa": False}
                if reason == "revoked"
                else (
                    {"fecha_vencimiento": clock[0]}
                    if reason == "expired"
                    else {"ultimo_acceso": clock[0] - app.config["AUTH_IDLE_TIMEOUT"]}
                )
            )
            db.session.execute(update(Sesion).values(**values))
        db.session.commit()
    response = client.get("/_test/identity")
    if reason == "permissions":
        assert response.json["admin"] is True
    else:
        assert response.json == {"authenticated": False}


def test_catalogo_no_renueva_actividad_ni_prolonga_sesion(navigation):
    _, client, clock, _ = navigation
    clock[0] += timedelta(minutes=29)
    assert client.get("/interface-catalog.js").status_code == 200
    clock[0] += timedelta(minutes=1)
    assert client.get("/_test/identity").json == {"authenticated": False}


def test_refresco_de_estadisticas_no_prolonga_sesion_por_inactividad(navigation):
    _, client, clock, _ = navigation
    clock[0] += timedelta(minutes=29)
    assert client.get("/auth/account/stats").status_code == 200
    clock[0] += timedelta(minutes=1)
    assert client.get("/_test/identity").json == {"authenticated": False}


def test_perfil_tras_renovar_actividad_no_relee_identidad_y_no_cachea_permisos(navigation):
    app, client, clock, engine = navigation
    clock[0] += timedelta(seconds=30)
    with database_work(engine) as work:
        response = client.get("/auth/account")
    assert response.status_code == 200
    assert work["sql"].count("SELECT") == 2
    assert work["sql"].count("UPDATE") == 1 and work["commits"] == 1
    with app.app_context():
        db.session.execute(update(Usuario).values(es_admin=True))
        db.session.commit()
    assert client.get("/_test/identity").json["admin"] is True
