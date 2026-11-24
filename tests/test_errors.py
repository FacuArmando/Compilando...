"""El error conserva su estado HTTP y permite volver a la plataforma."""

from html import unescape

import pytest

from compilando.i18n import COOKIE


@pytest.mark.parametrize("path", ["/una-pagina-que-no-existe", "/questions/999999"])
@pytest.mark.parametrize("language", ["es", "en"])
def test_pagina_inexistente_muestra_404_con_idioma_y_enlaces(client, path, language):
    client.set_cookie(COOKIE, language)
    response = client.get(path)

    assert response.status_code == 404
    assert response.mimetype == "text/html"
    assert f'<html lang="{language}">' in response.text
    assert (
        "We couldn't find this page." if language == "en" else "No encontramos esta página."
    ) in unescape(response.text)
    assert 'href="/"' in response.text
    assert 'href="/#preguntas"' in response.text
    assert "/static/img/errors/404-night.png" in response.text
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"


def test_404_no_expone_la_direccion_solicitada_ni_redirige_al_login(client):
    response = client.get("/no-existe?q=informacion-privada")
    assert response.status_code == 404
    assert "Location" not in response.headers
    assert "informacion-privada" not in response.text
    assert client.head("/no-existe").status_code == 404


def test_ilustracion_404_se_sirve_como_imagen(client):
    response = client.get("/static/img/errors/404-night.png")
    assert response.status_code == 200
    assert response.mimetype == "image/png"
