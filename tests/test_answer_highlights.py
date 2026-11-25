"""Destacados por lectores distintos, con ventana reciente y listado independiente."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import event

from compilando.extensions import db
from compilando.modules.answers.feedback import evaluar_respuesta
from compilando.modules.answers.highlights import preguntas_utiles_semana
from compilando.modules.answers.models import EvaluacionRespuesta
from compilando.modules.answers.services import publicar_respuesta
from compilando.modules.auth.models import Usuario
from compilando.modules.questions.services import publicar_pregunta

AHORA = datetime(2026, 11, 25, 18)


@pytest.fixture()
def lectores(app):
    usuarios = [
        Usuario(username=f"lector{n}", email=f"lector{n}@test.com", password_hash="prueba")
        for n in range(6)
    ]
    db.session.add_all(usuarios)
    db.session.commit()
    return usuarios


def respuesta(usuario, titulo):
    pregunta = publicar_pregunta(titulo, "Ejemplo para aprender.", "Java", [], usuario)
    return publicar_respuesta(pregunta.id, "Explicación del ejemplo.", usuario)


def votos(respuesta, lectores, dias=1, util=True):
    for lector in lectores:
        db.session.add(
            EvaluacionRespuesta(
                respuesta_id=respuesta.id,
                usuario_id=lector.id,
                util=util,
                fecha=AHORA - timedelta(days=20),
                fecha_actualizacion=AHORA - timedelta(days=dias),
            )
        )
    db.session.commit()


def test_cuenta_personas_distintas_y_retiros(usuario, lectores):
    primera = respuesta(usuario, "Una pregunta con alternativas")
    segunda = publicar_respuesta(primera.pregunta_id, "Otra explicación útil.", usuario)
    votos(primera, lectores[:1])
    votos(segunda, lectores[:1])
    assert preguntas_utiles_semana(AHORA) == []  # Dos respuestas, una sola persona.
    votos(primera, lectores[1:3])
    resultado = preguntas_utiles_semana(AHORA)
    assert len(resultado) == 1 and resultado[0].personas == 3
    evaluar_respuesta(segunda, lectores[0], False)
    assert preguntas_utiles_semana(AHORA)[0].personas == 3
    evaluar_respuesta(primera, lectores[1], None)
    assert preguntas_utiles_semana(AHORA) == []


def test_ventana_excluye_antiguos_futuros_y_negativos(usuario, lectores):
    for titulo, dias, util in [
        ("Antigua con votos", 8, True),
        ("Fecha futura de prueba", -1, True),
        ("Respuesta que no ayudó", 1, False),
    ]:
        votos(respuesta(usuario, titulo), lectores[:3], dias=dias, util=util)
    borde = respuesta(usuario, "En el límite de siete días")
    votos(borde, lectores[:3], dias=7)
    resultados = preguntas_utiles_semana(AHORA)
    assert [fila.pregunta_id for fila in resultados] == [borde.pregunta_id]
    fecha = db.session.get(EvaluacionRespuesta, (borde.id, lectores[0].id)).fecha_actualizacion
    evaluar_respuesta(borde, lectores[0], True)
    guardada = db.session.get(EvaluacionRespuesta, (borde.id, lectores[0].id))
    assert guardada.fecha_actualizacion == fecha


def test_orden_limite_y_consulta_unica(usuario, lectores):
    ids = []
    for n, cantidad in enumerate([3, 5, 4, 3]):
        publicacion = respuesta(usuario, f"Pregunta destacada {n}")
        votos(publicacion, lectores[:cantidad])
        ids.append(publicacion.pregunta_id)
    consultas = []

    def contar(conn, cursor, statement, *args):
        consultas.append(statement)

    event.listen(db.engine, "before_cursor_execute", contar)
    try:
        resultados = preguntas_utiles_semana(AHORA)
    finally:
        event.remove(db.engine, "before_cursor_execute", contar)
    assert [fila.pregunta_id for fila in resultados] == [ids[1], ids[2], ids[3]]
    assert [fila.personas for fila in resultados] == [5, 4, 3]
    assert len(consultas) == 1 and "respuestas.cuerpo" not in consultas[0]


def test_inicio_vacio_y_busqueda_sin_destacados(client, usuario):
    pregunta = respuesta(usuario, "Pregunta para filtrar")
    html = client.get("/").text
    assert 'id="highlights-title"' in html
    assert "Cuando más personas evalúen respuestas" in html
    for parametros in [{"q": "filtrar"}, {"categoria": pregunta.pregunta.categoria_id}]:
        assert 'id="highlights-title"' not in client.get("/", query_string=parametros).text
    client.set_cookie("compilando-language", "en")
    assert "Most helpful this week" in client.get("/").text


def test_tarjeta_destacada_con_datos_reales_y_titulo_escapado(
    monkeypatch, client, usuario, lectores
):
    publicacion = respuesta(usuario, "¿Cómo usar <b>Java</b>?")
    votos(publicacion, lectores[:3])
    monkeypatch.setattr(
        "compilando.modules.system.routes.preguntas_utiles_semana",
        lambda: preguntas_utiles_semana(AHORA),
    )
    html = client.get("/").text
    assert f'href="/questions/{publicacion.pregunta_id}#respuestas"' in html
    assert "Ayudó a 3 personas" in html
    assert "&lt;b&gt;Java&lt;/b&gt;" in html and "<b>Java</b>" not in html
    client.set_cookie("compilando-language", "en")
    assert "Helped 3 people" in client.get("/").text
