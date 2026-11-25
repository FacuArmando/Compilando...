"""Acentos y Unicode en las consultas reales; contenido original intacto."""

from html.parser import HTMLParser

import pytest
from sqlalchemy import func, select

from compilando import create_app
from compilando.extensions import db
from compilando.modules.questions.services import publicar_pregunta


@pytest.mark.parametrize("campo", ["titulo", "cuerpo", "etiqueta"])
@pytest.mark.parametrize("consulta", ["programacion", "PROGRAMACIÓN", "programacio\u0301n"])
def test_acentos_en_todos_los_campos_sin_reescribir(client, usuario, campo, consulta):
    titulo = "Conceptos de PROGRAMACIÓN" if campo == "titulo" else "Conceptos de objetos"
    cuerpo = "Ejemplo de programacio\u0301n." if campo == "cuerpo" else "Una explicación."
    tags = ["programación"] if campo == "etiqueta" else []
    pregunta = publicar_pregunta(titulo, cuerpo, "Java", tags, usuario)
    html = client.get("/", query_string={"q": consulta}).text
    assert 'aria-label="1 resultado"' in html
    assert f'href="/questions/{pregunta.id}"' in html
    db.session.refresh(pregunta)
    assert pregunta.titulo == titulo and pregunta.cuerpo_detallado == cuerpo
    if tags:
        assert pregunta.tags[0].nombre == tags[0]


def test_n_no_equivale_a_enie_y_mayusculas_unicode(client, usuario):
    enie = publicar_pregunta("Ejemplo del AÑO", "Una explicación.", "Java", [], usuario)
    ene = publicar_pregunta("Ejemplo del ano", "Otra explicación.", "Java", [], usuario)
    for consulta in ["año", "AÑO", "an\u0303o"]:
        html = client.get("/", query_string={"q": consulta}).text
        assert f'href="/questions/{enie.id}"' in html
        assert f'href="/questions/{ene.id}"' not in html
    html = client.get("/", query_string={"q": "ano"}).text
    assert f'href="/questions/{ene.id}"' in html
    assert f'href="/questions/{enie.id}"' not in html


def test_acento_repetido_no_aumenta_puntuacion(client, usuario):
    publicar_pregunta("Programación orientada a objetos", "Ejemplo en Java.", "Java", [], usuario)
    publicar_pregunta("Java orientado a objetos", "Ejemplo de programación.", "Java", [], usuario)
    respuestas = [
        client.get("/", query_string={"q": texto}).text
        for texto in ["programacion Java", "programación programacion Java"]
    ]

    class Enlaces(HTMLParser):
        def __init__(self, html):
            super().__init__()
            self.preguntas = []
            self.feed(html)

        def handle_starttag(self, tag, attrs):
            href = dict(attrs).get("href", "")
            if tag == "a" and href.removeprefix("/questions/").isdigit():
                self.preguntas.append(href)

    primera = Enlaces(respuestas[0]).preguntas
    segunda = Enlaces(respuestas[1]).preguntas
    assert len(primera) == 2 and primera == segunda


def test_consulta_solo_con_marcas_no_devuelve_todo(client, usuario):
    publicar_pregunta("Una pregunta publicada", "Una explicación.", "Java", [], usuario)
    html = client.get("/", query_string={"q": "\u0301"}).text
    assert "No encontramos preguntas" in html


def test_normalizador_en_conexiones_nuevas(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'conexion.sqlite'}",
        }
    )
    with app.app_context():
        try:
            for _ in range(2):
                resultado = db.session.scalar(
                    select(func.normalizar_busqueda("PROGRAMACIÓN ÑANDÚ C++ C# .NET"))
                )
                assert resultado == "programacion ñandu c++ c# .net"
                db.session.remove()
                db.engine.dispose()
        finally:
            db.session.remove()
            db.engine.dispose()
