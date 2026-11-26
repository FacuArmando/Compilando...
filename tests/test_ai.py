"""Solicitudes reales de Flask, con Gemini sustituido para no consumir la cuota."""

import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from html.parser import HTMLParser
from threading import Event

import pytest
from flask import session
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect, select, text, update

from compilando import create_app
from compilando.extensions import db
from compilando.modules.ai.models import SolicitudIA
from compilando.modules.ai.providers import MAX_RESPONSE_BYTES, ErrorIA, Gemini
from compilando.modules.ai.services import consultar_ia, preparar_contexto
from compilando.modules.answers.models import Respuesta
from compilando.modules.answers.services import editar_respuesta, publicar_respuesta
from compilando.modules.auth.models import Sesion, Usuario
from compilando.modules.auth.sessions import ahora_utc, iniciar_sesion
from compilando.modules.questions.models import Pregunta
from compilando.modules.questions.services import publicar_pregunta

JSON_HEADERS = {"Accept": "application/json"}


class TextoVisible(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.partes = []
        self.feed(html)

    def handle_data(self, data):
        self.partes.append(data)

    @property
    def texto(self):
        return "".join(self.partes)


class ProveedorPrueba:
    nombre = "Google Gemini"
    modelo = "modelo-de-prueba"

    def __init__(self):
        self.contextos = []
        self.error = None
        self.texto = "Una interfaz define un contrato.\n```java\ninterface Animal {}\n```"

    def responder(self, contexto):
        self.contextos.append(json.loads(contexto))
        if self.error:
            raise self.error
        return self.texto


@pytest.fixture
def app_ia(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "clave-exclusiva-de-pruebas-ia-1234567890",
            "GEMINI_API_KEY": "clave-solo-de-prueba",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'ia.sqlite'}",
            "QUESTION_UPLOAD_FOLDER": str(tmp_path / "adjuntos"),
        }
    )
    app.extensions["ai_provider"] = ProveedorPrueba()
    with app.app_context():
        upgrade()
        db.session.add_all(
            [
                Usuario(username="Mati", email="mati@example.test", password_hash="hash-prueba"),
                Usuario(username="Mili", email="mili@example.test", password_hash="hash-prueba"),
            ]
        )
        db.session.commit()
        pregunta = nueva_pregunta(1)
        assert pregunta.id == 1
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def nueva_pregunta(usuario_id=1, archivos=()):
    return publicar_pregunta(
        "¿Cómo se implementa una interfaz en Java?",
        "Tengo una clase Animal y quiero separar su contrato de la implementación.",
        "Java",
        ["interfaces"],
        db.session.get(Usuario, usuario_id),
        archivos=archivos,
    )


def cliente(app, usuario_id=1):
    cliente = app.test_client()
    if usuario_id:
        with app.test_request_context():
            iniciar_sesion(db.session.get(Usuario, usuario_id))
            token = session["auth_token"]
        with cliente.session_transaction() as datos:
            datos["auth_token"] = token
    return cliente


def csrf(cliente):
    pagina = cliente.get("/auth/login" if not cliente.get_cookie("compilando_session") else "/")
    return re.search(r'name="csrf_token"\s+value="([^"]+)"', pagina.get_data(as_text=True))[1]


def consultar(cliente, pregunta_id=1, *, headers=None, **datos):
    return cliente.post(
        f"/questions/{pregunta_id}/ai",
        data={"csrf_token": csrf(cliente), "confirmar_envio": "si", **datos},
        headers=JSON_HEADERS if headers is None else headers,
    )


def test_guarda_respuesta_y_solicitante_separados_sin_html_activo(app_ia):
    proveedor = app_ia.extensions["ai_provider"]
    proveedor.texto = "<img src=x onerror=alert(1)>\n```html\n<script>alert(2)</script>\n```"
    visitante = cliente(app_ia, 2)
    response = consultar(
        visitante, cuerpo="contenido inyectado", modelo="modelo-ajeno", usuario_id=1
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["cantidad"] == 1
    assert "&lt;img" in data["html"] and "&lt;script&gt;" in data["html"]
    assert "<script>" not in data["html"]
    assert "Editar respuesta" not in data["html"]
    assert "modelo-de-prueba" in data["html"]
    with app_ia.app_context():
        respuesta = db.session.get(Respuesta, data["respuesta_id"])
        assert respuesta.es_ia and respuesta.usuario_id is None
        assert respuesta.proveedor_ia == "Google Gemini"
        solicitud = db.session.get(SolicitudIA, 1)
        assert solicitud.solicitante_id == 2 and solicitud.respuesta_id == respuesta.id
        assert solicitud.estado == "completada"
    assert "contenido inyectado" not in str(proveedor.contextos)
    assert set(proveedor.contextos[0]) == {"titulo", "pregunta", "archivos"}
    publico = app_ia.test_client().get("/questions/1").get_data(as_text=True)
    assert "Ver respuesta de IA" not in publico  # El panel de consulta requiere sesión.
    assert "Generada por Google Gemini" in TextoVisible(publico).texto


def test_reutiliza_resultado_sin_llamar_otra_vez_y_admite_respuestas_humanas(app_ia):
    with app_ia.app_context():
        publicar_respuesta(
            1, "Una respuesta humana que debemos conservar.", db.session.get(Usuario, 1)
        )
    browser = cliente(app_ia)
    primero = consultar(browser)
    segundo = consultar(browser)
    assert primero.status_code == segundo.status_code == 200
    assert primero.json["respuesta_id"] == segundo.json["respuesta_id"]
    assert segundo.json["cantidad"] == 2
    assert len(app_ia.extensions["ai_provider"].contextos) == 1
    pagina = browser.get("/questions/1").get_data(as_text=True)
    assert "Ver respuesta de IA" in pagina and "form-consulta-ia" not in pagina


def test_sin_javascript_redirige_a_la_respuesta(app_ia):
    response = consultar(cliente(app_ia), headers={})
    assert response.status_code == 303 and "#respuesta-" in response.location


def test_exige_confirmacion_sesion_csrf_y_post(app_ia):
    browser = cliente(app_ia)
    assert browser.get("/questions/1/ai").status_code == 405
    assert consultar(browser, confirmar_envio="").status_code == 400
    response = browser.post("/questions/1/ai", data={"confirmar_envio": "si"}, headers=JSON_HEADERS)
    assert response.status_code == 400 and "formulario venció" in response.json["error"]
    visitante = cliente(app_ia, None)
    response = consultar(visitante)
    assert response.status_code == 401 and response.json["login_url"].startswith("/auth/login?")
    assert not app_ia.extensions["ai_provider"].contextos


@pytest.mark.parametrize("motivo", ["revocada", "vencida", "inactiva"])
def test_sesion_revalidada_antes_de_consumir_cuota(app_ia, motivo):
    browser = cliente(app_ia)
    token = csrf(browser)
    with app_ia.app_context():
        sesion = db.session.scalar(select(Sesion))
        if motivo == "revocada":
            sesion.activa = False
        elif motivo == "vencida":
            sesion.fecha_vencimiento = ahora_utc() - timedelta(seconds=1)
        else:
            sesion.ultimo_acceso = ahora_utc() - timedelta(hours=1)
        db.session.commit()
    response = browser.post(
        "/questions/1/ai", data={"csrf_token": token, "confirmar_envio": "si"}, headers=JSON_HEADERS
    )
    assert response.status_code == 401
    assert not app_ia.extensions["ai_provider"].contextos


def test_pregunta_inexistente_y_carga_enorme_no_llaman_proveedor(app_ia):
    browser = cliente(app_ia)
    assert consultar(browser, 999).status_code == 404
    assert consultar(browser, relleno="x" * 17000).status_code == 413
    assert not app_ia.extensions["ai_provider"].contextos


def test_no_configurada_no_reserva_consulta(app_ia):
    app_ia.extensions.pop("ai_provider")
    app_ia.config["GEMINI_API_KEY"] = ""
    response = consultar(cliente(app_ia))
    assert response.status_code == 503 and "no está configurada" in response.json["error"]
    with app_ia.app_context():
        assert db.session.get(SolicitudIA, 1) is None


def test_ingles_en_respuesta_asincrona_y_errores_sin_traducir_contenido(app_ia):
    browser = cliente(app_ia)
    browser.set_cookie("compilando-language", "en")
    response = consultar(browser)
    assert response.status_code == 200
    visible = TextoVisible(response.json["html"]).texto
    assert "Generated by Google Gemini" in visible
    assert "Una interfaz define un contrato." in visible
    assert "interface Animal {}" in visible

    expired = browser.post("/questions/1/ai", headers=JSON_HEADERS)
    assert expired.status_code == 400
    assert expired.json["error"] == "The form expired. Reload the page and try again."
    guest = cliente(app_ia, None)
    guest.set_cookie("compilando-language", "en")
    unauthorized = consultar(guest)
    assert unauthorized.status_code == 401
    assert unauthorized.json["error"] == "Sign in to ask AI."
    assert unauthorized.json["login_url"].startswith("/auth/login?")

    app_ia.extensions.pop("ai_provider")
    app_ia.config["GEMINI_API_KEY"] = ""
    with app_ia.app_context():
        otra = nueva_pregunta()
        pregunta_id = otra.id
    unavailable = consultar(browser, pregunta_id)
    assert unavailable.status_code == 503
    assert unavailable.json["error"] == "AI is not configured yet. Please let the team know."


@pytest.mark.parametrize("texto", ["", "x", "x" * 20001])
def test_no_guarda_resultados_vacios_o_excesivos_y_permite_reintento(app_ia, texto):
    proveedor = app_ia.extensions["ai_provider"]
    proveedor.texto = texto
    browser = cliente(app_ia)
    assert consultar(browser).status_code == 503
    with app_ia.app_context():
        assert db.session.scalar(select(Respuesta)) is None
        assert db.session.get(SolicitudIA, 1).estado == "error"
    proveedor.texto = "Una respuesta válida después del reintento."
    assert consultar(browser).status_code == 200
    assert len(proveedor.contextos) == 2


def test_error_proveedor_conserva_pregunta_y_no_publica_respuesta(app_ia):
    app_ia.extensions["ai_provider"].error = ErrorIA("La cuota de Gemini se agotó.", 429)
    response = consultar(cliente(app_ia))
    assert response.status_code == 429
    with app_ia.app_context():
        assert db.session.scalar(select(Respuesta)) is None
        assert db.session.get(SolicitudIA, 1).estado == "error"
    assert app_ia.test_client().get("/questions/1").status_code == 200


def test_cuota_por_usuario_persistente_y_reintentos_cuentan(app_ia):
    app_ia.config["AI_ACCOUNT_LIMIT"] = 1
    proveedor = app_ia.extensions["ai_provider"]
    proveedor.error = ErrorIA("Fallo temporal")
    browser = cliente(app_ia)
    assert consultar(browser).status_code == 503
    response = consultar(browser)
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
    assert len(proveedor.contextos) == 1


def test_cuota_global_comparte_limite_entre_usuarios(app_ia):
    app_ia.config["AI_GLOBAL_LIMIT"] = 1
    with app_ia.app_context():
        segunda_id = nueva_pregunta(2).id
    assert consultar(cliente(app_ia, 1)).status_code == 200
    assert consultar(cliente(app_ia, 2), segunda_id).status_code == 429
    assert len(app_ia.extensions["ai_provider"].contextos) == 1


def test_no_atribuye_ia_al_solicitante_ni_permite_editarla_incluso_legacy(app_ia):
    browser = cliente(app_ia)
    response = consultar(browser)
    respuesta_id = response.json["respuesta_id"]
    with app_ia.app_context():
        respuesta = db.session.get(Respuesta, respuesta_id)
        respuesta.usuario_id = 1  # Compatibilidad con filas IA del esquema anterior.
        db.session.commit()
        with pytest.raises(PermissionError):
            editar_respuesta(respuesta_id, "Intento de modificar la IA", db.session.get(Usuario, 1))
    response = browser.post(
        f"/answers/{respuesta_id}/edit",
        data={"csrf_token": csrf(browser), "cuerpo": "Intento de modificar la IA"},
    )
    assert response.status_code == 403
    assert "Editar respuesta" not in browser.get("/questions/1").get_data(as_text=True)


def test_adjuntos_solo_con_opcion_y_contexto_no_incluye_correo_o_contrasenia(app_ia):
    from werkzeug.datastructures import FileStorage

    with app_ia.app_context():
        p = nueva_pregunta(
            archivos=[
                FileStorage(stream=io.BytesIO(b"interface Animal {}"), filename="Animal.java")
            ]
        )
        sin = json.loads(preparar_contexto(p, False))
        con = json.loads(preparar_contexto(p, True))
        assert sin["archivos"] == []
        assert con["archivos"] == [{"nombre": "Animal.java", "codigo": "interface Animal {}"}]
        assert "email" not in con and "password_hash" not in con
        p.adjuntos[0].tamanio = 50 * 1024
        with pytest.raises(ErrorIA, match="48 KB"):
            preparar_contexto(p, True)
        p.adjuntos[0].tamanio = 20
        with pytest.raises(ErrorIA, match="leer"):
            preparar_contexto(p, True)


def test_contexto_mide_bytes_utf8_sin_recorte_silencioso(app_ia):
    with app_ia.app_context():
        p = db.session.get(Pregunta, 1)
        p.cuerpo_detallado = "á" * 25000
        with pytest.raises(ErrorIA, match="48 KB"):
            preparar_contexto(p, False)


def test_consultas_simultaneas_solo_una_llamada_y_una_respuesta(app_ia):
    entrando, terminar = Event(), Event()
    proveedor = app_ia.extensions["ai_provider"]
    responder = proveedor.responder

    def demorado(contexto):
        entrando.set()
        assert terminar.wait(10)
        return responder(contexto)

    proveedor.responder = demorado
    browser1, browser2 = cliente(app_ia, 1), cliente(app_ia, 2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        primero = executor.submit(consultar, browser1)
        assert entrando.wait(10)
        try:
            segundo = executor.submit(consultar, browser2).result(timeout=10)
            assert segundo.status_code == 409
        finally:
            terminar.set()
        assert primero.result(timeout=10).status_code == 200
    assert len(proveedor.contextos) == 1
    with app_ia.app_context():
        assert len(db.session.scalars(select(Respuesta)).all()) == 1


def test_consulta_abandonada_se_puede_reintentar_y_resultado_viejo_no_sobrescribe(app_ia):
    with app_ia.app_context():
        db.session.add(
            SolicitudIA(
                pregunta_id=1,
                solicitante_id=1,
                token="viejo",
                estado="pendiente",
                vence=ahora_utc() - timedelta(seconds=1),
            )
        )
        db.session.commit()
    assert consultar(cliente(app_ia)).status_code == 200
    with app_ia.app_context():
        assert db.session.get(SolicitudIA, 1).token != "viejo"


def test_reserva_que_vence_durante_llamada_no_publica_resultado(app_ia):
    proveedor = app_ia.extensions["ai_provider"]
    responder = proveedor.responder

    def vencido(contexto):
        db.session.execute(update(SolicitudIA).values(vence=ahora_utc() - timedelta(seconds=1)))
        db.session.commit()
        return responder(contexto)

    proveedor.responder = vencido
    assert consultar(cliente(app_ia)).status_code == 409
    with app_ia.app_context():
        assert db.session.scalar(select(Respuesta)) is None


def test_migracion_conserva_respuestas_humanas_y_ia_al_revertir(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "clave-de-prueba",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'migration.sqlite'}",
        }
    )
    with app.app_context():
        upgrade(revision="86c41e902ab7")
        db.session.execute(
            text("INSERT INTO usuarios VALUES (1, 'Mati', 'mati@example.test', 'hash')")
        )
        db.session.execute(text("INSERT INTO categorias VALUES (1, 'Java', 'Java')"))
        db.session.execute(
            text(
                "INSERT INTO preguntas "
                "(id, titulo, cuerpo_detallado, fecha, usuario_id, categoria_id) "
                "VALUES (1, 'Pregunta', 'Cuerpo', '2026-11-19', 1, 1)"
            )
        )
        db.session.execute(
            text(
                "INSERT INTO respuestas (id, cuerpo, fecha, pregunta_id, usuario_id) "
                "VALUES (1, 'Humana', '2026-11-19', 1, 1)"
            )
        )
        db.session.commit()
        upgrade()
        app.extensions["ai_provider"] = ProveedorPrueba()
        with app.test_request_context():
            respuesta = consultar_ia(1, 1, False)
            assert respuesta.usuario_id is None
        downgrade(revision="86c41e902ab7")
        filas = db.session.execute(
            text("SELECT cuerpo, usuario_id, es_ia FROM respuestas ORDER BY id")
        ).all()
        assert len(filas) == 2 and filas[0] == ("Humana", 1, 0)
        assert filas[1].usuario_id == 1 and filas[1].es_ia == 1
        upgrade()
        assert "solicitudes_ia" in inspect(db.engine).get_table_names()
        db.session.remove()
        db.engine.dispose()


class ConexionPrueba:
    def __init__(self, data=None, status=200, error=None):
        self.status = status
        self.data = json.dumps(data).encode() if data is not None else b""
        self.error = error
        self.cerrada = False
        self.solicitud = None

    def request(self, *args, **kwargs):
        self.solicitud = (args, kwargs)
        if self.error:
            raise self.error

    def getresponse(self):
        return self

    def read(self, limite):
        return self.data[:limite]

    def close(self):
        self.cerrada = True


def simular_transporte(monkeypatch, conexion):
    monkeypatch.setattr("compilando.modules.ai.providers.HTTPSConnection", lambda *a, **k: conexion)


def test_adaptador_envia_solo_lo_necesario_y_no_ejecuta_herramientas(monkeypatch):
    conexion = ConexionPrueba(
        {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [
                            {"thought": True, "text": "pensamiento privado"},
                            {"text": "Una respuesta de prueba"},
                        ]
                    },
                }
            ]
        }
    )
    simular_transporte(monkeypatch, conexion)
    proveedor = Gemini("clave-secreta-de-prueba")
    assert proveedor.responder("contexto") == "Una respuesta de prueba"
    args, kwargs = conexion.solicitud
    assert "clave-secreta-de-prueba" not in args[1]
    payload = json.loads(kwargs["body"])
    assert "tools" not in payload and "cachedContent" not in payload
    assert payload["generationConfig"]["maxOutputTokens"] == 1800
    assert payload["contents"] == [{"role": "user", "parts": [{"text": "contexto"}]}]
    assert args[1] == "/v1beta/models/gemini-3.5-flash-lite:generateContent"
    assert kwargs["headers"]["x-goog-api-key"] == "clave-secreta-de-prueba"
    assert "clave-secreta-de-prueba" not in repr(proveedor)
    assert conexion.cerrada


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500])
def test_errores_http_no_filtran_respuesta_o_clave(monkeypatch, status):
    conexion = ConexionPrueba({"secret": "detalle interno que no debe exponerse"}, status=status)
    simular_transporte(monkeypatch, conexion)
    with pytest.raises(ErrorIA) as error:
        Gemini("clave-no-publica").responder("pregunta")
    assert "detalle interno" not in str(error.value) and "clave-no-publica" not in str(error.value)
    assert error.value.status == (429 if status == 429 else 503)
    assert conexion.cerrada


@pytest.mark.parametrize(
    "data",
    [
        [],
        {"promptFeedback": {"blockReason": "SAFETY"}},
        {"candidates": []},
        {"candidates": [None]},
        {
            "candidates": [
                {"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "Incompleta"}]}}
            ]
        },
        {"candidates": [{"finishReason": "STOP", "content": {"parts": []}}]},
    ],
)
def test_adaptador_no_publica_respuestas_incompletas(monkeypatch, data):
    conexion = ConexionPrueba(data)
    simular_transporte(monkeypatch, conexion)
    with pytest.raises(ErrorIA):
        Gemini("clave-prueba").responder("pregunta")
    assert conexion.cerrada


@pytest.mark.parametrize("caso", ["timeout", "json", "limite"])
def test_adaptador_timeout_y_json_invalido_y_limite_de_lectura(monkeypatch, caso):
    conexion = ConexionPrueba(error=TimeoutError() if caso == "timeout" else None)
    conexion.data = b"x" * (MAX_RESPONSE_BYTES + 1) if caso == "limite" else b"no-json"
    simular_transporte(monkeypatch, conexion)
    with pytest.raises(ErrorIA):
        Gemini("clave-prueba").responder("pregunta")
    assert conexion.cerrada


def test_resultado_de_reserva_vieja_no_pisa_consulta_nueva(app_ia):
    entrando, terminar = Event(), Event()
    proveedor = app_ia.extensions["ai_provider"]
    llamadas = []

    def lento(contexto):
        llamadas.append(contexto)
        if len(llamadas) == 1:
            entrando.set()
            assert terminar.wait(10)
            return "Respuesta de una reserva vieja, no debe publicarse."
        return "Respuesta de la consulta nueva y vigente."

    proveedor.responder = lento
    primero, segundo = cliente(app_ia, 1), cliente(app_ia, 2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        resultado_viejo = executor.submit(consultar, primero)
        assert entrando.wait(10)
        try:
            with app_ia.app_context():
                db.session.execute(
                    update(SolicitudIA).values(vence=ahora_utc() - timedelta(seconds=1))
                )
                db.session.commit()
            assert executor.submit(consultar, segundo).result(timeout=10).status_code == 200
        finally:
            terminar.set()
        assert resultado_viejo.result(timeout=10).status_code == 409
    with app_ia.app_context():
        respuestas = db.session.scalars(select(Respuesta)).all()
        assert len(respuestas) == 1 and "nueva y vigente" in respuestas[0].cuerpo
        solicitud = db.session.get(SolicitudIA, 1)
        assert solicitud.estado == "completada" and solicitud.solicitante_id == 2


def test_carrera_al_crear_reserva_solo_consulta_una_vez(app_ia, monkeypatch):
    from threading import Barrier

    from compilando.modules.ai import services

    barrera = Barrier(2)
    limitar_original = services.limitar_intentos

    def limitar(*args, **kwargs):
        limitar_original(*args, **kwargs)
        barrera.wait(timeout=10)

    monkeypatch.setattr(services, "limitar_intentos", limitar)
    browser1, browser2 = cliente(app_ia, 1), cliente(app_ia, 2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(consultar, browser) for browser in (browser1, browser2)]
        statuses = sorted(f.result(timeout=10).status_code for f in futures)
    assert statuses == [200, 409]
    assert len(app_ia.extensions["ai_provider"].contextos) == 1


def test_fallo_guardando_no_deja_respuesta_parcial_y_libera_reserva(app_ia):
    from sqlalchemy import event
    from sqlalchemy.exc import IntegrityError

    def fallar(mapper, connection, target):
        raise IntegrityError("inserción simulada", {}, Exception("fallo de prueba"))

    browser = cliente(app_ia)
    event.listen(Respuesta, "before_insert", fallar)
    try:
        assert consultar(browser).status_code == 503
    finally:
        event.remove(Respuesta, "before_insert", fallar)
    with app_ia.app_context():
        assert db.session.scalar(select(Respuesta)) is None
        assert db.session.get(SolicitudIA, 1).estado == "error"
    assert consultar(browser).status_code == 200

def test_detectar_pregunta_requiere_ia_por_etiqueta(app, usuario):
    from compilando.modules.ai.services import detectar_pregunta_requiere_ia
    from compilando.modules.questions.services import publicar_pregunta

    pregunta = publicar_pregunta(
        titulo="¿Cómo optimizar esta consulta SQL?",
        cuerpo="Necesito ayuda con índices compuestos.",
        categoria_nombre="Bases de datos",
        nombres_tags=["sql", "ia"],
        usuario=usuario,
    )

    det = detectar_pregunta_requiere_ia(pregunta)
    assert det.requiere is True
    assert det.motivo == "etiqueta"


def test_detectar_pregunta_requiere_ia_por_tiempo_sin_respuesta(app, usuario):
    from datetime import date, timedelta
    from compilando.modules.ai.services import detectar_pregunta_requiere_ia
    from compilando.modules.questions.services import publicar_pregunta

    app.config["AI_UNANSWERED_MINUTES"] = 1440

    pregunta = publicar_pregunta(
        titulo="¿Diferencia entre proceso e hilo?",
        cuerpo="Explicación conceptual en sistemas operativos.",
        categoria_nombre="Sistemas Operativos",
        nombres_tags=["concurrencia"],
        usuario=usuario,
    )

    # Recién creada no requiere IA todavía
    assert detectar_pregunta_requiere_ia(pregunta).requiere is False

    # Pasadas más de 24 horas (2 días atrás) sin respuestas sí requiere IA
    pregunta.fecha = date.today() - timedelta(days=2)
    det = detectar_pregunta_requiere_ia(pregunta)
    assert det.requiere is True
    assert det.motivo == "tiempo_sin_respuesta"




def test_detectar_pregunta_no_requiere_ia_si_ya_tiene_respuesta_ia(app, usuario):
    from compilando.modules.ai.services import detectar_pregunta_requiere_ia
    from compilando.modules.answers.models import Respuesta
    from compilando.modules.questions.services import publicar_pregunta

    pregunta = publicar_pregunta(
        titulo="¿Cómo funciona async/await?",
        cuerpo="Duda sobre event loop en Python.",
        categoria_nombre="Python",
        nombres_tags=["ia"],
        usuario=usuario,
    )
    resp_ia = Respuesta(
        pregunta_id=pregunta.id,
        usuario_id=None,
        es_ia=True,
        cuerpo="Respuesta generada por IA.",
    )
    db.session.add(resp_ia)
    db.session.commit()

    det = detectar_pregunta_requiere_ia(pregunta)
    assert det.requiere is False
    assert det.motivo is None

def test_respuesta_automatica_ia_cuando_vence_tiempo(app, usuario):
    from datetime import date, timedelta
    from compilando.modules.ai.services import procesar_preguntas_vencidas_ia
    from compilando.modules.answers.models import Respuesta
    from compilando.modules.questions.services import publicar_pregunta

    app.config["AI_AUTO_RESPOND_UNANSWERED"] = True
    app.config["AI_AUTO_RESPOND_IN_TESTS"] = True
    app.config["AI_UNANSWERED_MINUTES"] = 1440

    class ProveedorFake:
        nombre = "gemini"
        modelo = "gemini-test"

        def responder(self, contexto: str) -> str:
            return "Respuesta automática generada por IA tras vencer el tiempo."

    app.extensions["ai_provider"] = ProveedorFake()

    pregunta = publicar_pregunta(
        titulo="¿Qué es un deadlock?",
        cuerpo="Necesito entender las 4 condiciones de Coffman.",
        categoria_nombre="Sistemas Operativos",
        nombres_tags=["procesos"],
        usuario=usuario,
    )

    # Recién creada: no genera respuesta automática
    assert procesar_preguntas_vencidas_ia() == 0

    # Simulamos que pasaron más de 24 horas (2 días atrás) sin respuestas
    pregunta.fecha = date.today() - timedelta(days=2)
    db.session.commit()

    with app.test_request_context("/"):
        generadas = procesar_preguntas_vencidas_ia()
    assert generadas == 1

    resp_ia = db.session.scalar(
        select(Respuesta).where(Respuesta.pregunta_id == pregunta.id, Respuesta.es_ia.is_(True))
    )
    assert resp_ia is not None
    assert "Respuesta automática generada por IA" in resp_ia.cuerpo

    # Una segunda ejecución no vuelve a generar duplicados
    with app.test_request_context("/"):
        assert procesar_preguntas_vencidas_ia() == 0
