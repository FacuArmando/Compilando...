"""Colección privada, orden persistente y protección de los formularios reales."""

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import session
from flask_migrate import downgrade, upgrade
from sqlalchemy import event, func, inspect, select
from sqlalchemy.exc import SQLAlchemyError

from compilando import create_app
from compilando.extensions import db
from compilando.modules.auth.models import Usuario
from compilando.modules.auth.sessions import iniciar_sesion
from compilando.modules.questions.models import Pregunta
from compilando.modules.questions.services import publicar_pregunta
from compilando.modules.saved.models import PreguntaGuardada

JSON = {"Accept": "application/json"}


@pytest.fixture
def saved_app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "clave-de-pruebas-guardadas",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'saved.sqlite'}",
        }
    )
    with app.app_context():
        upgrade()
        db.session.add_all(
            [
                Usuario(username="Uno", email="uno@example.test", password_hash="unused"),
                Usuario(username="Dos", email="dos@example.test", password_hash="unused"),
            ]
        )
        db.session.commit()
        for i in range(2):
            publicar_pregunta(
                f"Herencia Java caso {i}",
                "Un ejemplo.",
                "Java",
                ["java"],
                db.session.get(Usuario, 1),
            )
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def browser(app, user=1):
    client = app.test_client()
    if user:
        with app.test_request_context():
            iniciar_sesion(db.session.get(Usuario, user))
            token = session["auth_token"]
        with client.session_transaction() as state:
            state["auth_token"] = token
    return client


def csrf(client, path="/"):
    return re.search(r'name="csrf_token"\s+value="([^"]+)"', client.get(path).text)[1]


def change(client, question=1, choice="si", *, html=False, **data):
    return client.post(
        f"/questions/{question}/saved",
        data={
            "csrf_token": csrf(client),
            "guardada": choice,
            **data,
        },
        headers={} if html else JSON,
    )


def ids(response):
    return [
        int(value)
        for value in re.findall(
            r'<article class="community-question" id="pregunta-(\d+)"', response.text
        )
    ]


def test_visitante_ve_estrellas_y_se_autentica_para_abrir_guardadas(saved_app):
    client = browser(saved_app, None)
    assert "Sign in" not in client.get("/").text
    assert "Iniciá sesión para guardar preguntas." in client.get("/").text
    private = client.get("/saved")
    assert private.status_code == 303
    assert parse_qs(urlsplit(private.location).query)["next"] == ["/saved"]
    response = client.post(
        "/questions/1/saved",
        data={
            "csrf_token": csrf(client, "/auth/login"),
            "guardada": "si",
        },
        headers=JSON,
    )
    assert response.status_code == 401 and "login_url" in response.json
    with saved_app.app_context():
        assert db.session.scalar(select(func.count()).select_from(PreguntaGuardada)) == 0


def test_guardar_y_quitar_son_idempotentes_y_se_reflejan_en_todas_las_vistas(saved_app):
    client = browser(saved_app)
    assert change(client).json["guardada"] is True
    with saved_app.app_context():
        record = db.session.get(PreguntaGuardada, (1, 1))
        record.fecha = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=2)
        original = record.fecha
        db.session.commit()
    assert change(client).json["guardada"] is True
    with saved_app.app_context():
        assert db.session.scalar(select(func.count()).select_from(PreguntaGuardada)) == 1
        assert db.session.get(PreguntaGuardada, (1, 1)).fecha == original
    for path in ["/", "/questions/1", "/saved"]:
        html = client.get(path).text
        assert 'value="no" aria-pressed="true"' in html
        assert 'aria-label="Quitar de Guardadas"' in html
    assert change(client, choice="no").json["guardada"] is False
    assert change(client, choice="no").json["guardada"] is False
    assert ids(client.get("/saved")) == []
    assert "Todavía no guardaste preguntas" in client.get("/saved").text


def test_las_colecciones_son_privadas_y_no_se_puede_modificar_otro_usuario(saved_app):
    first, second = browser(saved_app), browser(saved_app, 2)
    assert change(first, 1).status_code == 200
    assert change(second, 2, usuario_id="1").status_code == 200
    assert ids(first.get("/saved")) == [1]
    assert ids(second.get("/saved")) == [2]
    assert change(second, 1, "no", usuario_id="1").json["guardada"] is False
    assert ids(first.get("/saved")) == [1]
    assert first.get("/saved").headers["Cache-Control"] == "no-store"
    assert "Cookie" in first.get("/saved").headers["Vary"]


def test_orden_de_guardado_y_volver_a_guardar_renueva_la_posicion(saved_app):
    client = browser(saved_app)
    change(client, 1)
    change(client, 2)
    with saved_app.app_context():
        now = datetime.now(UTC).replace(tzinfo=None)
        db.session.get(PreguntaGuardada, (1, 1)).fecha = now - timedelta(days=2)
        db.session.get(PreguntaGuardada, (1, 2)).fecha = now - timedelta(days=1)
        db.session.get(Pregunta, 2).fecha = (now - timedelta(days=90)).date()
        db.session.commit()
    assert ids(client.get("/saved")) == [2, 1]
    change(client, 1)
    assert ids(client.get("/saved")) == [2, 1]
    change(client, 1, "no")
    change(client, 1)
    assert ids(client.get("/saved")) == [1, 2]


def test_paginacion_privada_sin_omisiones_y_quitar_la_ultima_pagina(saved_app):
    with saved_app.app_context():
        prototype = db.session.get(Pregunta, 1)
        for n in range(3, 27):
            db.session.add(
                Pregunta(
                    titulo=f"Ejemplo de Java {n}",
                    cuerpo_detallado="Ejemplo.",
                    categoria_id=prototype.categoria_id,
                    usuario_id=1,
                )
            )
        db.session.flush()
        timestamp = datetime.now(UTC).replace(tzinfo=None)
        db.session.add_all(
            PreguntaGuardada(usuario_id=1, pregunta_id=n, fecha=timestamp) for n in range(1, 27)
        )
        db.session.commit()
    client = browser(saved_app)
    first, second = client.get("/saved"), client.get("/saved?page=2")
    assert ids(first) + ids(second) == list(range(26, 0, -1))
    assert len(ids(first)) == 20 and len(ids(second)) == 6
    next_url = re.search(r'rel="next" href="([^"]+)"', first.text)[1]
    assert urlsplit(next_url).path == "/saved" and "page=2" in next_url
    for question in range(1, 7):
        response = change(client, question, "no", html=True, volver="/saved?page=2")
        assert response.status_code == 303 and urlsplit(response.location).path == "/saved"
    empty = client.get("/saved?page=2")
    assert empty.status_code == 302 and "page=1" in empty.location
    assert len(ids(client.get(empty.location))) == 20


@pytest.mark.parametrize("value", ["0", "-1", "nada", str(2**80)])
def test_paginas_invalidas_se_normalizan(saved_app, value):
    assert browser(saved_app).get("/saved", query_string={"page": value}).status_code == 302


@pytest.mark.parametrize("token", [None, "inventado"])
def test_csrf_ausente_o_invalido_no_guarda(saved_app, token):
    client = browser(saved_app)
    response = client.post(
        "/questions/1/saved",
        data={
            "csrf_token": token,
            "guardada": "si",
        },
        headers=JSON,
    )
    assert response.status_code == 400
    assert "formulario venció" in response.json["error"]
    assert ids(client.get("/saved")) == []


def test_csrf_de_otro_navegador_no_guarda(saved_app):
    first, second = browser(saved_app), browser(saved_app, 2)
    other = csrf(second)
    csrf(first)
    response = first.post(
        "/questions/1/saved",
        data={
            "csrf_token": other,
            "guardada": "si",
        },
        headers=JSON,
    )
    assert response.status_code == 400 and ids(first.get("/saved")) == []


@pytest.mark.parametrize(
    "destination", ["https://ajeno.invalid", "//ajeno.invalid", "/auth/logout", "/\\ajeno.invalid"]
)
def test_el_regreso_no_redirige_a_destinos_ajenos(saved_app, destination):
    response = change(browser(saved_app), html=True, volver=destination)
    assert response.status_code == 303 and response.location == "/questions/1"


def test_formulario_normal_conserva_busqueda_y_categoria(saved_app):
    client = browser(saved_app)
    response = change(client, html=True, volver="/?q=Java%20C%2B%2B&categoria=1&page=2")
    destination = urlsplit(response.location)
    assert response.status_code == 303 and destination.path == "/"
    assert parse_qs(destination.query) == {"q": ["Java C++"], "categoria": ["1"], "page": ["2"]}
    assert destination.fragment == "pregunta-1"


def test_errores_no_modifican_la_coleccion(saved_app, monkeypatch):
    client = browser(saved_app)
    assert change(client, 999).status_code == 404
    assert change(client, 2**80).status_code == 404
    assert change(client, choice="toggle").status_code == 400
    assert client.get("/questions/1/saved").status_code == 405

    def fail(*args):
        raise SQLAlchemyError("error simulado")

    monkeypatch.setattr("compilando.modules.saved.routes.cambiar_guardado", fail)
    assert change(client).status_code == 503
    assert ids(client.get("/saved")) == []


def test_eliminar_pregunta_retira_sus_guardados(saved_app):
    change(browser(saved_app), 1)
    change(browser(saved_app, 2), 1)
    with saved_app.app_context():
        db.session.delete(db.session.get(Pregunta, 1))
        db.session.commit()
        assert db.session.scalar(select(func.count()).select_from(PreguntaGuardada)) == 0
    assert ids(browser(saved_app).get("/saved")) == []


def test_traduccion_y_regreso_del_login_a_guardadas(saved_app):
    client = browser(saved_app)
    client.set_cookie("compilando-language", "en")
    assert change(client).json["mensaje"] == "Question saved."
    html = client.get("/saved").text
    assert "Saved questions" in html and "Most recently saved first" in html
    assert 'aria-label="Remove from Saved"' in html
    response = client.get("/auth/login?next=/saved")
    assert response.location == "/saved"


def test_lecturas_de_guardadas_en_el_feed_se_agrupan(saved_app):
    client = browser(saved_app)
    change(client)
    with saved_app.app_context():
        statements = []

        def capture(connection, cursor, sql, parameters, context, executemany):
            if sql.lstrip().upper().startswith("SELECT"):
                statements.append(sql)

        event.listen(db.engine, "before_cursor_execute", capture)
        try:
            assert client.get("/").status_code == 200
        finally:
            event.remove(db.engine, "before_cursor_execute", capture)
        assert sum("FROM preguntas_guardadas" in sql for sql in statements) == 1
        assert len(statements) <= 10


def test_migracion_reversible_conserva_preguntas(saved_app):
    with saved_app.app_context():
        schema = inspect(db.engine)
        assert set(schema.get_pk_constraint("preguntas_guardadas")["constrained_columns"]) == {
            "usuario_id",
            "pregunta_id",
        }
        before = db.session.scalar(select(func.count()).select_from(Pregunta))
        downgrade(revision="73e2b91a6c04")
        assert "preguntas_guardadas" not in inspect(db.engine).get_table_names()
        assert db.session.scalar(select(func.count()).select_from(Pregunta)) == before
        upgrade()
        assert db.session.scalar(select(func.count()).select_from(PreguntaGuardada)) == 0
