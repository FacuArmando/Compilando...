from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest
from werkzeug.security import generate_password_hash

from compilando.extensions import db
from compilando.modules.categories.models import Categoria
from compilando.modules.questions.services import publicar_pregunta


class Feed(HTMLParser):
    """Leer los enlaces y controles que recibe el navegador después de integrar el feed."""

    def __init__(self, html):
        super().__init__()
        self.preguntas = []
        self.paginas = {}
        self.busqueda = None
        self.categoria = None
        self.ids = set()
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "a":
            ruta = urlsplit(attrs.get("href", "")).path
            if ruta.startswith("/questions/") and ruta.removeprefix("/questions/").isdigit():
                self.preguntas.append(int(ruta.removeprefix("/questions/")))
            if attrs.get("rel") in {"prev", "next"}:
                self.paginas[attrs["rel"]] = attrs["href"]
        if tag == "input" and attrs.get("name") == "q":
            self.busqueda = attrs.get("value")
        if tag == "option" and "selected" in attrs:
            self.categoria = attrs["value"]


def cliente_consulta(app, usuario, con_sesion):
    cliente = app.test_client()
    if con_sesion:
        usuario.password_hash = generate_password_hash("clave-prueba")
        db.session.commit()
        response = cliente.post(
            "/auth/login", data={"email": usuario.email, "password": "clave-prueba"}
        )
        assert response.status_code == 303
    return cliente


def test_consultar_preguntas_publicadas(app, usuario):
    publicar_pregunta(
        titulo="¿Cómo funciona Python?",
        cuerpo="Quiero aprender los fundamentos de este lenguaje.",
        categoria_nombre="Programación",
        nombres_tags=["python"],
        usuario=usuario,
    )

    publicar_pregunta(
        titulo="¿Cómo funciona Flask?",
        cuerpo="Quiero aprender a desarrollar aplicaciones web.",
        categoria_nombre="Desarrollo web",
        nombres_tags=["flask"],
        usuario=usuario,
    )

    cliente = app.test_client()
    response = cliente.get("/")

    assert response.status_code == 200
    assert b"Preguntas recientes" in response.data
    assert (
        b"Como funciona Python?" in response.data
        or "¿Cómo funciona Python?".encode() in response.data
    )
    assert "¿Cómo funciona Flask?".encode() in response.data

    posicion_flask = response.data.index("¿Cómo funciona Flask?".encode())
    posicion_python = response.data.index("¿Cómo funciona Python?".encode())

    assert posicion_flask < posicion_python


def test_consultar_preguntas_sin_publicaciones(app):
    cliente = app.test_client()
    response = cliente.get("/")

    assert response.status_code == 200
    assert "Todavía no hay preguntas publicadas.".encode() in response.data


@pytest.mark.parametrize("con_sesion", [False, True])
def test_feed_combina_busqueda_y_categoria_y_conserva_los_controles(app, usuario, con_sesion):
    pregunta = publicar_pregunta(
        "¿Cómo diseño un TAD?", "Quiero separar la interfaz y los datos.",
        "Estructuras", [], usuario,
    )
    publicar_pregunta(
        "¿Cómo diseño una cola?", "Quiero organizar sus operaciones.",
        "Estructuras", [], usuario,
    )
    publicar_pregunta(
        "¿Cómo diseño una interfaz web?", "Quiero organizar los botones.",
        "Desarrollo web", [], usuario,
    )
    cliente = cliente_consulta(app, usuario, con_sesion)
    response = cliente.get(
        "/", query_string={"q": "INTERFAZ", "categoria": pregunta.categoria_id}
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    feed = Feed(html)
    assert feed.preguntas == [pregunta.id]
    assert feed.busqueda == "INTERFAZ"
    assert feed.categoria == str(pregunta.categoria_id)
    assert 'aria-label="1 resultado"' in html
    assert ('id="question-composer"' in html) == con_sesion


@pytest.mark.parametrize("con_sesion", [False, True])
def test_feed_pagina_sin_perder_busqueda_ni_categoria(app, usuario, con_sesion):
    ids = []
    for numero in range(12):
        pregunta = publicar_pregunta(
            f"Pila de prueba {numero:02d}", "Quiero organizar sus operaciones.",
            "Estructuras", [], usuario,
        )
        ids.append(pregunta.id)
    categoria_id = db.session.scalar(
        db.select(Categoria.id).where(Categoria.nombre == "Estructuras")
    )
    publicar_pregunta(
        "Pila de otra categoría", "Una pregunta de desarrollo web.",
        "Desarrollo web", [], usuario,
    )
    cliente = cliente_consulta(app, usuario, con_sesion)
    primera = cliente.get("/", query_string={"q": "Pila", "categoria": categoria_id})
    assert primera.status_code == 200
    html = primera.get_data(as_text=True)
    feed = Feed(html)
    assert feed.preguntas == list(reversed(ids))[:10]
    assert 'aria-label="12 resultados"' in html
    assert "prev" not in feed.paginas
    enlace = urlsplit(feed.paginas["next"])
    assert parse_qs(enlace.query) == {
        "page": ["2"], "q": ["Pila"], "categoria": [str(categoria_id)]
    }
    segunda = cliente.get(f"{enlace.path}?{enlace.query}")
    assert segunda.status_code == 200
    feed_segunda = Feed(segunda.get_data(as_text=True))
    assert feed_segunda.preguntas == list(reversed(ids))[10:]
    assert "next" not in feed_segunda.paginas
    assert parse_qs(urlsplit(feed_segunda.paginas["prev"]).query)["page"] == ["1"]


@pytest.mark.parametrize("con_sesion", [False, True])
def test_feed_sin_coincidencias_conserva_y_escapa_la_busqueda(app, usuario, con_sesion):
    cliente = cliente_consulta(app, usuario, con_sesion)
    busqueda = '\"><script>alert(1)</script>'
    response = cliente.get("/", query_string={"q": busqueda})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "No encontramos preguntas" in html
    assert "<script>alert(1)</script>" not in html
    assert Feed(html).busqueda == busqueda
    assert Feed(html).preguntas == []


def test_busqueda_y_formulario_desplegable_no_comparten_identificadores(app, usuario):
    cliente = cliente_consulta(app, usuario, con_sesion=True)
    inicio = cliente.get("/")
    formulario = cliente.get("/questions/publish")
    assert inicio.status_code == formulario.status_code == 200
    ids_inicio = Feed(inicio.get_data(as_text=True)).ids
    ids_formulario = Feed(formulario.get_data(as_text=True)).ids
    # Al insertar el formulario en el inicio, cada label debe seguir apuntando a su campo.
    assert ids_inicio.isdisjoint(ids_formulario)
