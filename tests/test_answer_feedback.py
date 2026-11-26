"""Experiencia de utilidad por lector, sin modificar aceptación ni publicar negativos."""

from html.parser import HTMLParser

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import event, inspect, select, text
from sqlalchemy.exc import SQLAlchemyError

from compilando import create_app
from compilando.extensions import db
from compilando.modules.answers.feedback import evaluar_respuesta, resumen_evaluaciones
from compilando.modules.answers.models import EstadoRespuesta, EvaluacionRespuesta, Respuesta
from compilando.modules.answers.services import editar_respuesta, publicar_respuesta
from compilando.modules.auth.models import Usuario
from compilando.modules.questions.models import Pregunta
from compilando.modules.questions.services import publicar_pregunta


@pytest.fixture()
def respuesta_ajena(app, usuario):
    pregunta = publicar_pregunta(
        "¿Cómo funciona una interfaz?", "Necesito un ejemplo en Java.", "Java", [], usuario
    )
    autor = Usuario(username="quien_responde", email="respuesta@test.com", password_hash="prueba")
    db.session.add(autor)
    db.session.commit()
    return publicar_respuesta(pregunta.id, "La interfaz define un contrato.", autor)


class BotonesFeedback(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.botones = []
        self.particulas = []
        self.en_formulario = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("class") == "feedback-particle":
            self.particulas.append(attrs)
        if tag == "form":
            self.en_formulario = attrs.get("class") == "answer-feedback-form"
        if tag == "button" and self.en_formulario:
            self.botones.append(attrs)

    def handle_endtag(self, tag):
        if tag == "form":
            self.en_formulario = False


def test_evaluar_cambiar_repetir_y_retirar(client, cliente_autenticado, usuario, respuesta_ajena):
    respuesta = respuesta_ajena
    ruta = f"/answers/{respuesta.id}/feedback"
    detalle = f"/questions/{respuesta.pregunta_id}"
    cliente = cliente_autenticado(usuario)

    for opcion, esperado in [("si", True), ("si", True), ("no", False), ("si", True)]:
        response = cliente.post(ruta, data={"utilidad": opcion})
        assert response.status_code == 303
        assert response.location.endswith(f"{detalle}#respuesta-{respuesta.id}")
        filas = db.session.scalars(select(EvaluacionRespuesta)).all()
        assert len(filas) == 1 and filas[0].util is esperado
        assert db.session.get(Respuesta, respuesta.id).estado == EstadoRespuesta.NO_ACEPTADA.value
        pagina = cliente.get(detalle)
        botones = BotonesFeedback(pagina.text).botones
        assert [b["aria-pressed"] for b in botones] == (
            ["true", "false"] if esperado else ["false", "true"]
        )
        assert botones[0 if esperado else 1]["value"] == "retirar"
        assert ("A 1 persona le ayudó" in pagina.text) is esperado
        if not esperado:
            assert "answer-feedback-count" not in pagina.text

    for _ in range(2):
        assert cliente.post(ruta, data={"utilidad": "retirar"}).status_code == 303
        assert db.session.scalars(select(EvaluacionRespuesta)).all() == []
    assert BotonesFeedback(cliente.get(detalle).text).botones[0]["aria-pressed"] == "false"


def test_confeti_compatible_con_politica_de_estilos(cliente_autenticado, usuario, respuesta_ajena):
    cliente = cliente_autenticado(usuario)
    response = cliente.get(f"/questions/{respuesta_ajena.pregunta_id}")
    assert response.status_code == 200
    politica = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in politica and "unsafe-inline" not in politica
    particulas = BotonesFeedback(response.text).particulas
    assert particulas and all("style" not in particula for particula in particulas)
    assert cliente.get("/static/css/answers.css").status_code == 200


def test_permisos_y_entradas_invalidas(client, cliente_autenticado, usuario, respuesta_ajena):
    respuesta = respuesta_ajena
    ruta = f"/answers/{respuesta.id}/feedback"
    assert client.post(ruta, data={"utilidad": "si"}).status_code == 401
    autor = cliente_autenticado(respuesta.usuario)
    assert autor.post(ruta, data={"utilidad": "si"}).status_code == 403
    assert not BotonesFeedback(autor.get(f"/questions/{respuesta.pregunta_id}").text).botones
    lector = cliente_autenticado(usuario)
    for datos in [{}, {"utilidad": "quizá"}, {"utilidad": "1"}]:
        assert lector.post(ruta, data=datos).status_code == 400
    assert lector.post("/answers/999999/feedback", data={"utilidad": "si"}).status_code == 404
    assert db.session.scalars(select(EvaluacionRespuesta)).all() == []


def test_formulario_exige_csrf(app, cliente_autenticado, usuario, respuesta_ajena):
    cliente = cliente_autenticado(usuario)
    app.config["WTF_CSRF_ENABLED"] = True
    assert (
        cliente.post(f"/answers/{respuesta_ajena.id}/feedback", data={"utilidad": "si"}).status_code
        == 400
    )
    assert db.session.scalars(select(EvaluacionRespuesta)).all() == []


def test_feedback_json_actualiza_estado_y_conteo_sin_flash(
    cliente_autenticado, usuario, respuesta_ajena
):
    cliente = cliente_autenticado(usuario)
    cliente.set_cookie("compilando-language", "en")
    ruta = f"/answers/{respuesta_ajena.id}/feedback"
    for opcion, eleccion, cantidad in [
        ("si", True, 1),
        ("si", True, 1),
        ("no", False, 0),
        ("retirar", None, 0),
    ]:
        response = cliente.post(
            ruta, data={"utilidad": opcion}, headers={"Accept": "application/json"}
        )
        assert response.status_code == 200 and response.is_json
        assert response.json == {
            "respuesta_id": respuesta_ajena.id,
            "utilidad": eleccion,
            "cantidad_utiles": cantidad,
            "mensaje": (
                "You removed your feedback." if eleccion is None else "Thanks for your feedback."
            ),
        }
    with cliente.session_transaction() as sesion:
        assert not sesion.get("_flashes")


def test_feedback_json_errores_y_csrf(app, client, cliente_autenticado, usuario, respuesta_ajena):
    ruta = f"/answers/{respuesta_ajena.id}/feedback"
    headers = {"Accept": "application/json"}
    assert client.post(ruta, data={"utilidad": "si"}, headers=headers).status_code == 401
    autor = cliente_autenticado(respuesta_ajena.usuario)
    response = autor.post(ruta, data={"utilidad": "si"}, headers=headers)
    assert response.status_code == 403 and response.json["error"]
    lector = cliente_autenticado(usuario)
    lector.set_cookie("compilando-language", "en")
    for destino, datos, estado in [
        (ruta, {"utilidad": "quizá"}, 400),
        ("/answers/999999/feedback", {"utilidad": "si"}, 404),
    ]:
        response = lector.post(destino, data=datos, headers=headers)
        assert response.status_code == estado and response.is_json and response.json["error"]
    app.config["WTF_CSRF_ENABLED"] = True
    response = lector.post(ruta, data={"utilidad": "si"}, headers=headers)
    assert response.status_code == 400 and response.is_json
    assert "Your form expired" in response.json["error"]
    assert db.session.scalars(select(EvaluacionRespuesta)).all() == []


def test_feedback_json_fallo_de_guardado_no_confirma(
    monkeypatch, cliente_autenticado, usuario, respuesta_ajena
):
    def fallo(*args):
        raise SQLAlchemyError("fallo simulado")

    monkeypatch.setattr("compilando.modules.answers.routes.evaluar_respuesta", fallo)
    response = cliente_autenticado(usuario).post(
        f"/answers/{respuesta_ajena.id}/feedback",
        data={"utilidad": "si"},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 503 and response.json["error"]
    assert "utilidad" not in response.json
    assert db.session.scalars(select(EvaluacionRespuesta)).all() == []


def test_ia_visitantes_traducciones_y_conteo_privado(
    client, cliente_autenticado, usuario, respuesta_ajena
):
    respuesta = respuesta_ajena
    respuesta.es_ia = True
    respuesta.usuario = None
    respuesta.modelo_ia = "Modelo de prueba"
    db.session.commit()
    cliente = cliente_autenticado(usuario)
    cliente.set_cookie("compilando-language", "en")
    ruta = f"/answers/{respuesta.id}/feedback"
    detalle = f"/questions/{respuesta.pregunta_id}"
    assert cliente.post(ruta, data={"utilidad": "si"}).status_code == 303
    pagina = cliente.get(detalle)
    assert "This helped 1 person" in pagina.text and "Thanks for your feedback." in pagina.text
    assert "Did this answer help you?" in pagina.text
    assert len(BotonesFeedback(pagina.text).botones) == 2
    visitante = client.get(detalle)
    assert "A 1 persona le ayudó" in visitante.text
    assert "Ingresá para dar tu opinión" in visitante.text
    assert not BotonesFeedback(visitante.text).botones
    cliente.post(ruta, data={"utilidad": "no"})
    assert "answer-feedback-count" not in client.get(detalle).text


def test_edicion_conserva_evaluaciones_y_borrado_las_elimina(usuario, respuesta_ajena):
    respuesta = respuesta_ajena
    evaluar_respuesta(respuesta, usuario, True)
    editar_respuesta(respuesta.id, "Explicación corregida con un ejemplo.", respuesta.usuario)
    assert db.session.get(EvaluacionRespuesta, (respuesta.id, usuario.id)).util is True
    db.session.delete(respuesta)
    db.session.commit()
    assert db.session.scalars(select(EvaluacionRespuesta)).all() == []


def test_conteos_agrupados_y_eleccion_personal(usuario, respuesta_ajena):
    respuesta = respuesta_ajena
    evaluar_respuesta(respuesta, usuario, True)
    otra = Respuesta(cuerpo="Una alternativa de IA.", pregunta=respuesta.pregunta, es_ia=True)
    db.session.add(otra)
    db.session.commit()
    evaluar_respuesta(otra, usuario, False)
    evaluar_respuesta(otra, respuesta.usuario, True)
    respuestas = db.session.scalars(select(Respuesta).order_by(Respuesta.id)).all()
    usuario_id = usuario.id
    consultas = []

    def contar(*args):
        consultas.append(args[2])

    event.listen(db.engine, "before_cursor_execute", contar)
    try:
        resumen = resumen_evaluaciones(respuestas, usuario)
    finally:
        event.remove(db.engine, "before_cursor_execute", contar)
    assert len(consultas) == 2
    assert resumen == {respuesta.id: (1, True), otra.id: (1, False)}
    assert resumen_evaluaciones(respuestas, None) == {respuesta.id: (1, None), otra.id: (1, None)}
    assert db.session.get(Usuario, usuario_id) is usuario


def test_migracion_conserva_publicaciones(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "solo-pruebas",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'evaluaciones.sqlite'}",
        }
    )
    with app.app_context():
        upgrade(revision="f681d3b207ac")
        usuario = Usuario(username="lector", email="lector@test.com", password_hash="prueba")
        db.session.add(usuario)
        db.session.commit()
        # Insertar las columnas históricas, anteriores a los campos de búsqueda.
        categoria_id = db.session.scalar(
            text("INSERT INTO categorias (nombre, descripcion) VALUES ('Java', '') RETURNING id")
        )
        pregunta_id = db.session.scalar(
            text(
                "INSERT INTO preguntas (titulo, cuerpo_detallado, fecha, usuario_id, categoria_id) "
                "VALUES ('Pregunta previa', 'Contenido previo.', CURRENT_DATE, :u, :c) RETURNING id"
            ),
            {"u": usuario.id, "c": categoria_id},
        )
        respuesta = publicar_respuesta(pregunta_id, "Respuesta previa.", usuario)
        respuesta_id = respuesta.id
        db.session.remove()
        try:
            upgrade()
            assert "evaluaciones_respuestas" in inspect(db.engine).get_table_names()
            clave = inspect(db.engine).get_pk_constraint("evaluaciones_respuestas")
            assert clave["constrained_columns"] == ["respuesta_id", "usuario_id"]
            assert db.session.get(Pregunta, pregunta_id).titulo == "Pregunta previa"
            assert db.session.get(Respuesta, respuesta_id).cuerpo == "Respuesta previa."
            db.session.remove()
            downgrade(revision="f681d3b207ac")
            assert "evaluaciones_respuestas" not in inspect(db.engine).get_table_names()
            assert db.session.get(Respuesta, respuesta_id).cuerpo == "Respuesta previa."
            db.session.remove()
            upgrade()
            assert "evaluaciones_respuestas" in inspect(db.engine).get_table_names()
        finally:
            db.session.remove()
            db.engine.dispose()
