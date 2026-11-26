"""Sugerencias reales, orden coherente con el listado y consultas acotadas."""

from datetime import date, timedelta

import pytest
from flask import template_rendered
from sqlalchemy import event

from compilando.extensions import db
from compilando.modules.answers.models import EstadoRespuesta, Respuesta
from compilando.modules.questions.services import publicar_pregunta


def test_sugerencias_publicas_coinciden_con_el_orden_del_listado(app, client, usuario):
    for i in range(7):
        publicar_pregunta(f"Herencia Java caso {i}", "Ejemplos.", "Java", ["java"], usuario)
    antigua = publicar_pregunta(
        "Herencia Java aceptada", "Ejemplos.", "Java", ["java", "javascript"], usuario
    )
    antigua.fecha = date.today() - timedelta(days=30)
    db.session.add(
        Respuesta(
            pregunta_id=antigua.id,
            usuario_id=usuario.id,
            cuerpo="Solución",
            estado=EstadoRespuesta.ACEPTADA.value,
        )
    )
    publicar_pregunta("Mención incidental", "Herencia Java.", "Java", [], usuario)
    db.session.commit()
    orden = []

    def capturar(sender, template, context, **extra):
        orden.extend(p.id for p in context["preguntas"])

    with template_rendered.connected_to(capturar, app):
        assert client.get("/", query_string={"q": "herencia java"}).status_code == 200
    response = client.get("/search/suggestions", query_string={"q": "herencia java"})
    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert response.headers["Cache-Control"] == "no-store"
    preguntas = response.json["preguntas"]
    assert len(preguntas) == 5
    assert [p["id"] for p in preguntas] == orden[:5]
    assert preguntas[0]["id"] == antigua.id
    for pregunta in preguntas:
        assert set(pregunta) == {"id", "titulo", "categoria", "url"}
        assert pregunta["url"] == f"/questions/{pregunta['id']}"
        assert client.get(pregunta["url"]).status_code == 200


def test_sugerencias_respetan_categoria_acentos_y_equivalencia(client, usuario):
    java = publicar_pregunta(
        "Programación orientada a objetos Java", "Ejemplos.", "Java", [], usuario
    )
    publicar_pregunta("POO Python", "Ejemplos.", "Python", [], usuario)
    for consulta in ["POO", "programacion orientada a objetos", "programación"]:
        response = client.get(
            "/search/suggestions", query_string={"q": consulta, "categoria": java.categoria_id}
        )
        assert [p["id"] for p in response.json["preguntas"]] == [java.id]
    assert client.get(
        "/search/suggestions", query_string={"q": "POO", "categoria": 99999}
    ).json == {"preguntas": []}


@pytest.mark.parametrize("consulta", ["", "ja", "   ja  ", "x" * 201, "java " * 13])
def test_consultas_fuera_de_limite_no_acceden_a_la_base(app, client, consulta):
    consultas = []

    def contar(connection, cursor, statement, parameters, context, executemany):
        consultas.append(statement)

    event.listen(db.engine, "before_cursor_execute", contar)
    try:
        assert client.get("/search/suggestions", query_string={"q": consulta}).json == {
            "preguntas": []
        }
    finally:
        event.remove(db.engine, "before_cursor_execute", contar)
    assert consultas == []


@pytest.mark.parametrize("categoria", ["incorrecta", "0", "-1", str(2**80)])
def test_categoria_invalida_no_amplia_resultados(client, usuario, categoria):
    publicar_pregunta("Herencia Java", "Ejemplos.", "Java", [], usuario)
    response = client.get("/search/suggestions", query_string={"q": "java", "categoria": categoria})
    assert response.status_code == 400
    assert response.json == {"preguntas": []}


@pytest.mark.parametrize("consulta", ["C++", ".NET", "%_%"])
def test_sugerencias_respetan_simbolos_literales(client, usuario, consulta):
    pregunta = publicar_pregunta(f"Ejemplos de {consulta}", "Contenido.", "Java", [], usuario)
    publicar_pregunta("Una pregunta distinta", "Contenido.", "Java", [], usuario)
    response = client.get("/search/suggestions", query_string={"q": consulta})
    assert [p["id"] for p in response.json["preguntas"]] == [pregunta.id]


def test_sugerencias_usan_una_consulta_y_solo_campos_publicos(app, client, usuario):
    publicar_pregunta("Herencia Java", "CUERPO PRIVADO DEL DESPLEGABLE", "Java", [], usuario)
    consultas = []

    def contar(connection, cursor, statement, parameters, context, executemany):
        consultas.append(statement)

    event.listen(db.engine, "before_cursor_execute", contar)
    try:
        response = client.get("/search/suggestions", query_string={"q": "java"})
    finally:
        event.remove(db.engine, "before_cursor_execute", contar)
    assert len(consultas) == 1
    assert "LIMIT" in consultas[0]
    assert "CUERPO PRIVADO DEL DESPLEGABLE" not in response.text
    assert usuario.email not in response.text


def test_textos_de_usuarios_son_datos_y_no_se_traducen(client, usuario):
    titulo = "Python <script>alert(1)</script>"
    publicar_pregunta(titulo, "Ejemplos.", "Python", [], usuario)
    client.set_cookie("compilando-language", "en")
    assert client.get("/search/suggestions?q=python").json["preguntas"][0]["titulo"] == titulo
    html = client.get("/").text
    assert 'id="navbar-search-options" role="listbox"' in html
    assert 'aria-label="Suggested questions"' in html
    assert "Related questions" in html and "See all results" in html
    assert 'id="navbar-search-status" role="status"' in html
    assert "js/search-autocomplete.js" in html and "css/search-autocomplete.css" in html
    assert client.post("/search/suggestions").status_code == 405
