"""Idiomas de interfaz sin alterar contenido, autenticación ni archivos."""

import io
import json
from html.parser import HTMLParser

import pytest
from flask import render_template_string

from compilando.i18n import CATALOG, COOKIE, i18n_attr, ui
from compilando.modules.answers.services import publicar_respuesta
from compilando.modules.questions.services import publicar_pregunta


class Visible(HTMLParser):
    def __init__(self, response):
        super().__init__()
        self.parts = []
        self.feed(response.get_data(as_text=True))
        self.text = "".join(self.parts)

    def handle_data(self, data):
        self.parts.append(data)


def test_idioma_por_defecto_y_cookie_invalida(client):
    for value in [None, "fr", '<img src=x onerror="alert(1)">']:
        if value:
            client.set_cookie(COOKIE, value)
        response = client.get("/auth/login")
        assert response.status_code == 200
        assert '<html lang="es">' in response.text
        assert "Iniciar sesión" in Visible(response).text


def test_ingles_persiste_en_navegacion_y_errores(client):
    client.set_cookie(COOKIE, "en")
    for path, text in [
        ("/", "Recent questions"),
        ("/auth/login", "Sign in"),
        ("/auth/register", "Create an account"),
    ]:
        response = client.get(path)
        assert response.status_code == 200
        assert '<html lang="en">' in response.text
        assert text in Visible(response).text
    response = client.post("/auth/login", data={"email": "nobody@example.test", "password": "bad"})
    assert response.status_code == 401
    assert "Incorrect credentials." in Visible(response).text
    assert 'value="nobody@example.test"' in response.text
    assert 'value="bad"' not in response.text
    assert client.get("/auth/account").status_code == 303


def test_ingles_no_traduce_preguntas_respuestas_categorias_usuarios(
    app,
    usuario,
    cliente_autenticado,
):
    pregunta = publicar_pregunta("Mi cuenta Inicio", "Inicio", "Inicio", ["Mi cuenta"], usuario)
    publicar_respuesta(pregunta.id, "Mostrar contraseña", usuario)
    client = cliente_autenticado(usuario)
    client.set_cookie(COOKIE, "en")
    response = client.get(f"/questions/{pregunta.id}")
    assert response.status_code == 200
    visible = Visible(response).text
    assert "Your answer" in visible and "1 answer" in visible
    assert "Mi cuenta Inicio" in visible
    assert "Mostrar contraseña" in visible
    assert 'class="question-full-body">Inicio</div>' in response.text
    assert 'class="question-detail-tags"' in response.text
    assert "usuario_test" in visible
    account = client.get("/auth/account")
    assert "My account" in Visible(account).text
    assert "usuario@test.com" in Visible(account).text
    assert "hash_de_prueba" not in account.text


def test_validacion_archivos_en_ingles_escapa_nombre_y_conserva_datos(
    usuario,
    cliente_autenticado,
):
    client = cliente_autenticado(usuario)
    client.set_cookie(COOKIE, "en")
    response = client.post(
        "/questions/publish",
        data={
            "titulo": "Pregunta que permanece",
            "cuerpo": "Inicio",
            "categoria": "Java",
            "archivos": (io.BytesIO(b"binary"), "file<script>.exe"),
        },
    )
    assert response.status_code == 400
    assert "choose one of these file types" in Visible(response).text
    assert "file&lt;script&gt;.exe" in response.text
    assert "file<script>" not in response.text
    assert 'value="Pregunta que permanece"' in response.text
    assert ">Inicio</textarea>" in response.text


def test_mensajes_y_atributos_escapan_parametros_sin_html_activo(app):
    evil = '"><img src=x onerror=alert(1)>{count}'
    with app.test_request_context(headers={"Cookie": f"{COOKIE}=en"}):
        text = str(ui("Respuesta de {name}", name=evil))
        attr = str(i18n_attr("aria-label", "Código de {name}", name=evil))
        assert "<img" not in text and "<img" not in attr
        assert "&lt;img" in text and "{count}" in text
        assert "Answer by" in text
        assert "Code in" in attr
        with pytest.raises(ValueError):
            i18n_attr("onclick", "Inicio")
        assert render_template_string("{{ value }}", value="<script>") == "&lt;script&gt;"


def test_catalogo_publico_solo_contiene_interfaz(client):
    response = client.get("/interface-catalog.js")
    assert response.status_code == 200
    assert response.mimetype == "text/javascript"
    catalog = json.loads(response.text.removeprefix("window.CompilandoCatalog=").removesuffix(";"))
    assert catalog == CATALOG
    assert catalog["Inicio"] == "Home"
    assert "Set-Cookie" not in response.headers
