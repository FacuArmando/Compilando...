"""Sugerencias explícitas y equivalencias sin ampliar silenciosamente una búsqueda."""

from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest

from compilando.extensions import db
from compilando.modules.categories.models import Categoria
from compilando.modules.questions.services import publicar_pregunta
from compilando.modules.tags.models import Tag


class Sugerencias(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.activa = False
        self.enlaces = []
        self.busqueda = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "p" and attrs.get("class") == "community-search-suggestion":
            self.activa = True
        if tag == "a" and self.activa:
            self.enlaces.append(attrs["href"])
        if tag == "input" and attrs.get("name") == "q":
            self.busqueda = attrs.get("value")

    def handle_endtag(self, tag):
        if tag == "p":
            self.activa = False


@pytest.mark.parametrize("error", ["pyhton", "pyton", "pythonn", "pythom"])
def test_sugerencia_requiere_click_y_conserva_categoria(client, usuario, error):
    pregunta = publicar_pregunta(
        "Aprender Python con ejemplos", "Una explicación.", "Python", ["python"], usuario
    )
    response = client.get("/", query_string={"q": error, "categoria": pregunta.categoria_id})
    assert response.status_code == 200 and 'aria-label="0 resultados"' in response.text
    parser = Sugerencias(response.text)
    assert parser.busqueda == error and len(parser.enlaces) == 1
    enlace = parser.enlaces[0]
    query = parse_qs(urlsplit(enlace).query)
    assert query["q"] == ["python"]
    assert query["categoria"] == [str(pregunta.categoria_id)]
    assert urlsplit(enlace).fragment == "preguntas" and "page" not in query
    assert 'aria-label="1 resultado"' in client.get(enlace).text
    client.set_cookie("compilando-language", "en")
    assert "Did you mean" in client.get("/", query_string={"q": error}).text


def test_no_sugiere_fuera_de_categoria_ni_con_resultados(client, usuario):
    publicar_pregunta("Aprender Python con ejemplos", "Una explicación.", "Python", [], usuario)
    otra = publicar_pregunta("Ejemplo de contratos Java", "Una explicación.", "Java", [], usuario)
    html = client.get("/", query_string={"q": "pyhton", "categoria": otra.categoria_id}).text
    assert Sugerencias(html).enlaces == []
    publicar_pregunta("Una publicación sobre pyhton", "Texto literal.", "Python", [], usuario)
    html = client.get("/", query_string={"q": "pyhton"}).text
    assert 'aria-label="1 resultado"' in html and Sugerencias(html).enlaces == []


def test_no_sugiere_opciones_ambiguas_o_sin_publicaciones(client, usuario):
    db.session.add(Categoria(nombre="Python", descripcion="Sin publicaciones"))
    db.session.commit()
    assert Sugerencias(client.get("/", query_string={"q": "pyhton"}).text).enlaces == []
    publicar_pregunta("Aprender Python con ejemplos", "Una explicación.", "Python", [], usuario)
    db.session.add(Tag(nombre="pythin"))
    db.session.commit()
    assert Sugerencias(client.get("/", query_string={"q": "pythun"}).text).enlaces == []


@pytest.mark.parametrize("consulta", ["C++", "C#", ".NET", "jav", "pina"])
def test_no_corrige_simbolos_terminos_cortos_ni_enie(client, usuario, consulta):
    publicar_pregunta(
        "Tecnologías disponibles", "Una explicación.", "Java", ["piña", "net"], usuario
    )
    assert Sugerencias(client.get("/", query_string={"q": consulta}).text).enlaces == []


@pytest.mark.parametrize("consulta", ["POO Java", "programación orientada a objetos Java"])
def test_equivalencia_poo_bidireccional_y_otros_terminos(client, usuario, consulta):
    abreviada = publicar_pregunta(
        "Conceptos de POO en Java", "Una explicación.", "Java", [], usuario
    )
    completa = publicar_pregunta(
        "Conceptos de programación orientada a objetos", "Ejemplos Java.", "Java", [], usuario
    )
    publicar_pregunta("Conceptos de POO en Python", "Una explicación.", "Python", [], usuario)
    html = client.get("/", query_string={"q": consulta}).text
    assert 'aria-label="2 resultados"' in html
    for pregunta in (abreviada, completa):
        assert f'href="/questions/{pregunta.id}"' in html
    assert Sugerencias(html).busqueda == consulta


def test_articulos_opcionales_sin_ampliar_consulta_vacia(client, usuario):
    pregunta = publicar_pregunta(
        "Herencia Java con ejemplos", "Una explicación.", "Java", [], usuario
    )
    html = client.get("/", query_string={"q": "la herencia de Java"}).text
    assert 'aria-label="1 resultado"' in html and f'href="/questions/{pregunta.id}"' in html
    html = client.get("/", query_string={"q": "de la en"}).text
    assert 'aria-label="0 resultados"' in html
    assert "Escribí una tecnología, tema o concepto para buscar." in html
    assert Sugerencias(html).enlaces == []
