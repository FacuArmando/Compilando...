"""Recorridos reales de autenticación y rechazo de intentos de evadir sus controles."""

import hashlib
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import g, request
from flask_migrate import downgrade, upgrade
from sqlalchemy import delete, inspect, select, update
from werkzeug.security import generate_password_hash

from compilando import create_app
from compilando.extensions import db
from compilando.modules.auth.models import LimiteIntentos, Sesion, Usuario
from compilando.modules.auth.services import (
    ERROR_CREDENCIALES,
    autenticar_usuario,
    registrar_usuario,
)
from compilando.modules.auth.sessions import ahora_utc, requiere_sesion

PASSWORD = "clave-prueba"
EMAIL = "mati@ejemplo.com"
SECRET = "clave-aleatoria-exclusiva-de-pruebas-1234567890"


@pytest.fixture
def app_login(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": SECRET,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'login.sqlite'}",
        }
    )
    with app.app_context():
        upgrade()
        registrar_usuario("Mati", EMAIL, PASSWORD)
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


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


class Formulario(HTMLParser):
    def __init__(self):
        super().__init__()
        self.campos = {}

    def handle_starttag(self, tag, attrs):
        atributos = dict(attrs)
        if tag == "input":
            self.campos[atributos["name"]] = atributos


def campos(response):
    formulario = Formulario()
    formulario.feed(response.get_data(as_text=True))
    return formulario.campos


class Enlaces(HTMLParser):
    def __init__(self, response):
        super().__init__()
        self.enlaces = []
        self.feed(response.get_data(as_text=True))

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.enlaces.append(dict(attrs))


def ingresar(cliente, email=EMAIL, password=PASSWORD, *, ip="127.0.0.1", headers=None):
    opciones = {"environ_overrides": {"REMOTE_ADDR": ip}}
    token = campos(cliente.get("/auth/login", follow_redirects=True, **opciones))["csrf_token"][
        "value"
    ]
    return cliente.post(
        "/auth/login",
        data={"email": email, "password": password, "csrf_token": token},
        headers=headers,
        **opciones,
    )


def sesion_cookie(app, cliente):
    return cliente.get_cookie(app.config["SESSION_COOKIE_NAME"]).value


@pytest.fixture
def pregunta_con_sesion(app_login):
    from compilando.modules.questions.services import publicar_pregunta

    with app_login.app_context():
        usuario = db.session.scalar(select(Usuario).where(Usuario.email == EMAIL))
        pregunta = publicar_pregunta(
            titulo="¿Cómo se implementa un tipo abstracto de datos?",
            cuerpo="Quiero distinguir la interfaz de un TAD de su implementación.",
            categoria_nombre="Programación",
            nombres_tags=["TADs", "Python"],
            usuario=usuario,
        )
        return pregunta.id


def test_inicio_publico_y_login_son_pantallas_separadas(app_login, pregunta_con_sesion):
    cliente = app_login.test_client()
    inicio = cliente.get("/")
    assert inicio.status_code == 200
    html = inicio.get_data(as_text=True)
    assert f'href="/questions/{pregunta_con_sesion}"' in html
    assert 'class="community-navbar-search"' in html
    assert 'class="auth-form"' not in html
    assert 'id="login-title"' not in html
    assert 'id="question-composer"' not in html

    for ruta in ["/auth/login", "/auth/register"]:
        acceso = cliente.get(ruta)
        assert acceso.status_code == 200
        assert 'class="auth-form"' in acceso.get_data(as_text=True)
        assert 'id="preguntas"' not in acceso.get_data(as_text=True)
        assert 'class="community-navbar-search"' not in acceso.get_data(as_text=True)
        assert f'href="/questions/{pregunta_con_sesion}"' not in acceso.get_data(as_text=True)


def test_visitante_vuelve_a_preguntar_despues_del_login(app_login):
    cliente = app_login.test_client()
    enlace = next(
        item["href"]
        for item in Enlaces(cliente.get("/")).enlaces
        if "composer-guest" in item.get("class", "").split()
    )
    assert parse_qs(urlsplit(enlace).query)["next"] == ["/#question-composer"]
    formulario = cliente.get(enlace)
    datos = {
        "csrf_token": campos(formulario)["csrf_token"]["value"],
        "next": campos(formulario)["next"]["value"],
        "email": EMAIL,
        "password": "incorrecta",
    }
    error = cliente.post("/auth/login", data=datos)
    assert error.status_code == 401
    assert campos(error)["next"]["value"] == "/#question-composer"
    with cliente.session_transaction() as estado:
        assert "auth_token" not in estado
    datos["password"] = PASSWORD
    datos["csrf_token"] = campos(error)["csrf_token"]["value"]
    ingreso = cliente.post("/auth/login", data=datos)
    assert ingreso.status_code == 303
    assert ingreso.headers["Location"] == "/#question-composer"
    inicio = cliente.get("/")
    assert 'id="question-composer"' in inicio.get_data(as_text=True)
    csrf = campos(inicio)["csrf_token"]["value"]
    salida = cliente.post("/auth/logout", data={"csrf_token": csrf}, follow_redirects=True)
    assert salida.status_code == 200
    assert 'class="auth-form"' not in salida.get_data(as_text=True)
    assert "composer-guest" in salida.get_data(as_text=True)


def test_visitante_vuelve_a_responder_despues_del_login(app_login, pregunta_con_sesion):
    cliente = app_login.test_client()
    ruta = f"/questions/{pregunta_con_sesion}"
    enlace = next(
        item["href"]
        for item in Enlaces(cliente.get(ruta)).enlaces
        if item.get("class") == "question-reply-link"
    )
    destino = f"{ruta}#tu-respuesta"
    assert parse_qs(urlsplit(enlace).query)["next"] == [destino]
    formulario = cliente.get(enlace)
    datos = {
        "csrf_token": "incorrecto",
        "next": campos(formulario)["next"]["value"],
        "email": EMAIL,
        "password": PASSWORD,
    }
    error = cliente.post("/auth/login", data=datos)
    assert error.status_code == 400
    assert campos(error)["next"]["value"] == destino
    datos["csrf_token"] = campos(error)["csrf_token"]["value"]
    ingreso = cliente.post("/auth/login", data=datos)
    assert ingreso.status_code == 303
    assert ingreso.headers["Location"] == destino
    detalle = cliente.get(ruta)
    assert 'id="form-respuesta-usuario"' in detalle.get_data(as_text=True)
    respuesta = cliente.post(
        f"{ruta}/answers",
        data={"csrf_token": campos(detalle)["csrf_token"]["value"], "cuerpo": "Mi solución."},
    )
    assert respuesta.status_code == 302
    assert "Mi solución." in cliente.get(ruta).get_data(as_text=True)


def test_registro_desde_login_conserva_la_pregunta_a_responder(app_login, pregunta_con_sesion):
    cliente = app_login.test_client()
    destino = f"/questions/{pregunta_con_sesion}#tu-respuesta"
    login = cliente.get("/auth/login", query_string={"next": destino})
    registro_url = next(
        item["href"]
        for item in Enlaces(login).enlaces
        if urlsplit(item["href"]).path == "/auth/register"
    )
    registro = cliente.get(registro_url)
    response = cliente.post(
        "/auth/register",
        data={
            "csrf_token": campos(registro)["csrf_token"]["value"],
            "next": campos(registro)["next"]["value"],
            "username": "Nuevo visitante",
            "email": "nuevo@ejemplo.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 303
    assert response.headers["Location"] == destino
    with cliente.session_transaction() as estado:
        assert "auth_token" in estado
    detalle = cliente.get(response.headers["Location"])
    assert 'id="form-respuesta-usuario"' in detalle.get_data(as_text=True)
    assert campos(detalle)["csrf_token"]["value"] != campos(registro)["csrf_token"]["value"]
    respuesta = cliente.post(
        f"/questions/{pregunta_con_sesion}/answers",
        data={"csrf_token": campos(detalle)["csrf_token"]["value"], "cuerpo": "Mi solución."},
    )
    assert respuesta.status_code == 302
    assert "Mi solución." in cliente.get(destino).get_data(as_text=True)
    salida = cliente.post(
        "/auth/logout", data={"csrf_token": campos(detalle)["csrf_token"]["value"]}
    )
    assert salida.status_code == 303
    formulario = cliente.get("/auth/login")
    ingreso = cliente.post(
        "/auth/login",
        data={
            "csrf_token": campos(formulario)["csrf_token"]["value"],
            "email": "nuevo@ejemplo.com",
            "password": PASSWORD,
        },
    )
    assert ingreso.status_code == 303
    assert cliente.get("/auth/account").status_code == 200


def test_login_con_sesion_vuelve_al_destino_sin_pedir_credenciales(app_login, pregunta_con_sesion):
    cliente = app_login.test_client()
    assert ingresar(cliente).status_code == 303
    destino = f"/questions/{pregunta_con_sesion}#tu-respuesta"
    response = cliente.get("/auth/login", query_string={"next": destino})
    assert response.status_code == 302
    assert response.headers["Location"] == destino


@pytest.mark.parametrize(
    "destino",
    [
        "https://ajeno.invalid",
        "//ajeno.invalid",
        "/\\ajeno.invalid",
        "javascript:alert(1)",
        "/auth/login",
        "/auth/logout",
        "/health",
        "/no-existe",
        "/questions/1?next=//ajeno.invalid",
        "/#ajeno",
        "/%2f%2fajeno.invalid",
        "\n//ajeno.invalid",
        "https://[",
        "/questions/1#tu-respuesta\r\nX-test:1",
    ],
)
def test_regreso_del_login_rechaza_destinos_externos_o_no_permitidos(app_login, destino):
    cliente = app_login.test_client()
    formulario = cliente.get("/auth/login", query_string={"next": destino})
    assert formulario.status_code == 200
    assert campos(formulario)["next"]["value"] == "/"
    response = cliente.post(
        "/auth/login",
        data={
            "csrf_token": campos(formulario)["csrf_token"]["value"],
            "next": destino,
            "email": EMAIL,
            "password": PASSWORD,
        },
    )
    assert response.status_code == 303
    assert response.headers["Location"] == "/"


def test_visitante_no_publica_con_url_directa_aunque_tenga_csrf(app_login, pregunta_con_sesion):
    from compilando.modules.answers.models import Respuesta
    from compilando.modules.questions.models import Pregunta

    cliente = app_login.test_client()
    csrf = campos(cliente.get("/auth/login"))["csrf_token"]["value"]
    assert cliente.get("/questions/publish").status_code == 401
    pregunta = cliente.post(
        "/questions/publish",
        data={"csrf_token": csrf, "titulo": "Intento sin sesión", "cuerpo": "Mi pregunta."},
    )
    respuesta = cliente.post(
        f"/questions/{pregunta_con_sesion}/answers",
        data={"csrf_token": csrf, "cuerpo": "Intento sin sesión."},
    )
    assert pregunta.status_code == respuesta.status_code == 401
    with app_login.app_context():
        assert len(db.session.scalars(select(Pregunta)).all()) == 1
        assert db.session.scalar(select(Respuesta.id)) is None


def test_detalle_de_pregunta_se_puede_leer_sin_iniciar_sesion(app_login, pregunta_con_sesion):
    response = app_login.test_client().get(f"/questions/{pregunta_con_sesion}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Quiero distinguir la interfaz de un TAD" in html
    assert "/auth/login?next=" in html
    assert 'id="form-respuesta-usuario"' not in html
    assert "Sesión iniciada como" not in html


def test_abrir_pregunta_desde_inicio_conserva_la_sesion(app_login, pregunta_con_sesion):
    cliente = app_login.test_client()
    assert ingresar(cliente).status_code == 303
    inicio = cliente.get("/")
    assert f'href="/questions/{pregunta_con_sesion}"' in inicio.get_data(as_text=True)
    with cliente.session_transaction() as estado:
        token_original = estado["auth_token"]

    for ruta in [f"/questions/{pregunta_con_sesion}", "/auth/account", "/"]:
        response = cliente.get(ruta)
        assert response.status_code == 200
        assert "Sesión iniciada como Mati" in TextoVisible(response.get_data(as_text=True)).texto
        with cliente.session_transaction() as estado:
            assert estado["auth_token"] == token_original


def test_responder_desde_detalle_no_pide_otro_login(app_login, pregunta_con_sesion):
    cliente = app_login.test_client()
    assert ingresar(cliente).status_code == 303
    ruta = f"/questions/{pregunta_con_sesion}"
    detalle = cliente.get(ruta)
    assert 'id="form-respuesta-usuario"' in detalle.get_data(as_text=True)
    csrf = campos(detalle)["csrf_token"]["value"]

    response = cliente.post(
        f"{ruta}/answers",
        data={"csrf_token": csrf, "cuerpo": "Respuesta nueva sin volver a ingresar."},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == ruta
    html = cliente.get(ruta).get_data(as_text=True)
    assert "Tu respuesta fue publicada correctamente." in html
    assert "Respuesta nueva sin volver a ingresar." in html
    assert "Sesión iniciada como Mati" in TextoVisible(html).texto


@pytest.mark.parametrize("motivo", ["vencimiento", "inactividad"])
def test_detalle_pide_login_para_responder_solo_si_la_sesion_vencio(
    app_login, pregunta_con_sesion, motivo
):
    cliente = app_login.test_client()
    assert ingresar(cliente).status_code == 303
    with app_login.app_context():
        sesion = db.session.scalar(select(Sesion))
        if motivo == "vencimiento":
            sesion.fecha_vencimiento = ahora_utc() - timedelta(seconds=1)
        else:
            sesion.ultimo_acceso = ahora_utc() - timedelta(minutes=31)
        db.session.commit()

    response = cliente.get(f"/questions/{pregunta_con_sesion}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="form-respuesta-usuario"' not in html
    assert "Sesión iniciada como" not in html
    with cliente.session_transaction() as estado:
        assert "auth_token" not in estado


def test_respuesta_desde_detalle_conserva_csrf(app_login, pregunta_con_sesion):
    from compilando.modules.answers.models import Respuesta

    cliente = app_login.test_client()
    assert ingresar(cliente).status_code == 303
    response = cliente.post(
        f"/questions/{pregunta_con_sesion}/answers",
        data={"csrf_token": "incorrecto", "cuerpo": "No debe guardarse."},
    )
    assert response.status_code == 400
    with app_login.app_context():
        assert db.session.scalar(select(Respuesta.id)) is None


def test_detalle_y_edicion_respetan_el_autor_de_la_respuesta(app_login, pregunta_con_sesion):
    from compilando.modules.answers.models import Respuesta
    from compilando.modules.answers.services import publicar_respuesta

    with app_login.app_context():
        propio = db.session.scalar(select(Usuario).where(Usuario.email == EMAIL))
        otro = registrar_usuario("Otro autor", "otro@ejemplo.com", PASSWORD)
        respuesta_propia = publicar_respuesta(pregunta_con_sesion, "Mi respuesta.", propio)
        respuesta_ajena = publicar_respuesta(
            pregunta_con_sesion, "Respuesta de otra persona.", otro
        )
        id_propia, id_ajena = respuesta_propia.id, respuesta_ajena.id

    cliente = app_login.test_client()
    assert ingresar(cliente).status_code == 303
    detalle = cliente.get(f"/questions/{pregunta_con_sesion}")
    html = detalle.get_data(as_text=True)
    assert f'id="form-editar-respuesta-{id_propia}"' in html
    assert f'id="form-editar-respuesta-{id_ajena}"' not in html
    csrf = campos(detalle)["csrf_token"]["value"]
    response = cliente.post(
        f"/answers/{id_ajena}/edit",
        data={"csrf_token": csrf, "cuerpo": "Intento de edición ajena."},
    )
    assert response.status_code == 403
    with app_login.app_context():
        assert db.session.get(Respuesta, id_ajena).cuerpo == "Respuesta de otra persona."


def test_login_lee_cuenta_crea_sesion_y_muestra_nombre(app_login):
    cliente = app_login.test_client()
    response = ingresar(cliente, email="  MATI@EJEMPLO.COM  ")
    assert response.status_code == 303
    assert response.headers["Location"] == "/"
    with cliente.session_transaction() as estado:
        assert set(estado) == {"auth_token", "_permanent"}
        token = estado["auth_token"]
    with app_login.app_context():
        sesion = db.session.scalar(select(Sesion))
        assert sesion.id == hashlib.sha256(token.encode()).hexdigest()
        assert token != sesion.id
        assert sesion.activa
        assert sesion.fecha_vencimiento > sesion.fecha_inicio
        assert len(db.session.scalars(select(Usuario)).all()) == 1
    inicio = cliente.get("/")
    assert "Sesión iniciada como Mati" in TextoVisible(inicio.get_data(as_text=True)).texto
    assert "Cerrar sesión" in inicio.get_data(as_text=True)
    assert PASSWORD not in inicio.get_data(as_text=True)
    assert cliente.get("/auth/login").status_code == 302
    assert "HttpOnly" in response.headers["Set-Cookie"]
    assert "SameSite=Lax" in response.headers["Set-Cookie"]


def test_mi_cuenta_muestra_datos_propios_sin_exponer_credenciales(app_login):
    cliente = app_login.test_client()
    assert ingresar(cliente).status_code == 303
    assert 'href="/auth/account"' in cliente.get("/").get_data(as_text=True)

    response = cliente.get("/auth/account")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Mi cuenta" in html
    assert "Nombre de usuario" in html
    assert "Correo electrónico" in html
    assert "Mati" in html and EMAIL in html
    assert PASSWORD not in html
    assert response.headers["Cache-Control"] == "no-store"
    with app_login.app_context():
        usuario = db.session.scalar(select(Usuario).where(Usuario.email == EMAIL))
        assert usuario.password_hash not in html


@pytest.mark.parametrize("metodo", ["GET", "HEAD"])
def test_mi_cuenta_sin_sesion_redirige_al_login(app_login, metodo):
    response = app_login.test_client().open("/auth/account", method=metodo)
    assert response.status_code == 303
    assert response.headers["Location"] == "/auth/login"
    assert EMAIL not in response.get_data(as_text=True)


def test_mi_cuenta_ignora_identidades_enviadas_en_la_url(app_login):
    with app_login.app_context():
        otro = registrar_usuario("Otra persona", "otra@ejemplo.com", PASSWORD)
        otro_id = otro.id
    cliente = app_login.test_client()
    assert ingresar(cliente).status_code == 303

    response = cliente.get(f"/auth/account?usuario_id={otro_id}&email=otra@ejemplo.com")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert EMAIL in html
    assert "otra@ejemplo.com" not in html
    assert "Otra persona" not in html


@pytest.mark.parametrize("motivo", ["vencimiento", "inactividad", "revocacion", "cookie"])
def test_mi_cuenta_rechaza_sesiones_invalidas(app_login, motivo):
    cliente = app_login.test_client()
    assert ingresar(cliente).status_code == 303
    if motivo == "cookie":
        cliente.set_cookie(
            app_login.config["SESSION_COOKIE_NAME"], sesion_cookie(app_login, cliente) + "alterada"
        )
    else:
        with app_login.app_context():
            sesion = db.session.scalar(select(Sesion))
            if motivo == "vencimiento":
                sesion.fecha_vencimiento = ahora_utc() - timedelta(seconds=1)
            elif motivo == "inactividad":
                sesion.ultimo_acceso = ahora_utc() - timedelta(minutes=31)
            else:
                sesion.activa = False
            db.session.commit()

    response = cliente.get("/auth/account")
    assert response.status_code == 303
    assert response.headers["Location"] == "/auth/login"
    assert EMAIL not in response.get_data(as_text=True)


def test_mi_cuenta_es_de_consulta_y_no_acepta_modificaciones(app_login):
    cliente = app_login.test_client()
    assert ingresar(cliente).status_code == 303
    token = campos(cliente.get("/auth/account"))["csrf_token"]["value"]
    with app_login.app_context():
        hash_original = db.session.scalar(
            select(Usuario.password_hash).where(Usuario.email == EMAIL)
        )

    response = cliente.post(
        "/auth/account",
        data={
            "csrf_token": token,
            "username": "modificado",
            "email": "modificado@ejemplo.com",
            "password": "nueva-clave",
        },
    )
    assert response.status_code == 405
    with app_login.app_context():
        usuario = db.session.scalar(select(Usuario).where(Usuario.email == EMAIL))
        assert usuario.username == "Mati"
        assert usuario.email == EMAIL
        assert usuario.password_hash == hash_original


def test_mi_cuenta_escapa_el_nombre_del_usuario(app_login):
    with app_login.app_context():
        usuario = db.session.scalar(select(Usuario).where(Usuario.email == EMAIL))
        usuario.username = "Mati <script>alert(1)</script>"
        db.session.commit()
    cliente = app_login.test_client()
    assert ingresar(cliente).status_code == 303

    html = cliente.get("/auth/account").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "Mati &lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_cerrar_sesion_desde_mi_cuenta_impide_volver_a_ver_los_datos(app_login):
    cliente = app_login.test_client()
    assert ingresar(cliente).status_code == 303
    token = campos(cliente.get("/auth/account"))["csrf_token"]["value"]
    assert cliente.post("/auth/logout", data={"csrf_token": token}).status_code == 303
    assert cliente.get("/auth/account").status_code == 303


@pytest.mark.parametrize(
    ("email", "password"),
    [
        (EMAIL, "contraseña-incorrecta"),
        ("no-existe@ejemplo.com", PASSWORD),
        ("' OR 1=1 --", PASSWORD),
        ("", PASSWORD),
        (EMAIL, ""),
        (EMAIL, "x" * 129),
        ("x" * 255, PASSWORD),
    ],
)
def test_credenciales_invalidas_siempre_rechazan_sin_autenticar(app_login, email, password):
    cliente = app_login.test_client()
    response = ingresar(cliente, email=email, password=password)
    assert response.status_code == 401
    assert ERROR_CREDENCIALES in response.get_data(as_text=True)
    assert "value" not in campos(response)["password"]
    with cliente.session_transaction() as estado:
        assert "auth_token" not in estado
    with app_login.app_context():
        assert db.session.scalars(select(Sesion)).all() == []


@pytest.mark.parametrize("longitud", [13, 128])
def test_login_conserva_acceso_con_contrasenas_anteriores(app_login, longitud):
    password = "p" * longitud
    with app_login.app_context():
        usuario = db.session.scalar(select(Usuario).where(Usuario.email == EMAIL))
        usuario.password_hash = generate_password_hash(password)
        db.session.commit()

    cliente = app_login.test_client()
    formulario = cliente.get("/auth/login")
    assert int(campos(formulario)["password"]["maxlength"]) >= longitud
    assert ingresar(cliente, password=password).status_code == 303


def test_contrasena_con_espacios_se_comprueba_sin_recortarla(app_login):
    with app_login.app_context():
        registrar_usuario("otro", "otro@ejemplo.com", " clave123 ")
        assert autenticar_usuario("otro@ejemplo.com", " clave123 ").username == "otro"
        with pytest.raises(ValueError, match=ERROR_CREDENCIALES):
            autenticar_usuario("otro@ejemplo.com", "clave123")


def test_cuenta_inexistente_tambien_comprueba_un_hash(app_login, monkeypatch):
    from compilando.modules.auth import services

    comprobaciones = []
    comprobar = services.check_password_hash

    def registrar_comprobacion(hash_guardado, password):
        comprobaciones.append(hash_guardado)
        return comprobar(hash_guardado, password)

    monkeypatch.setattr(services, "check_password_hash", registrar_comprobacion)
    response = ingresar(app_login.test_client(), email="nadie@ejemplo.com")
    assert response.status_code == 401
    assert len(comprobaciones) == 1
    assert comprobaciones[0].startswith("scrypt:")


@pytest.mark.parametrize("token", [None, "incorrecto"])
def test_login_rechaza_csrf_ausente_o_incorrecto(app_login, token):
    cliente = app_login.test_client()
    cliente.get("/auth/login")
    data = {"email": EMAIL, "password": PASSWORD}
    if token is not None:
        data["csrf_token"] = token
    response = cliente.post("/auth/login", data=data)
    assert response.status_code == 400
    assert "Iniciar sesión" in response.get_data(as_text=True)
    assert "El formulario venció o no es válido" in response.get_data(as_text=True)
    assert "value" not in campos(response)["password"]
    with app_login.app_context():
        assert db.session.scalars(select(Sesion)).all() == []


def test_csrf_de_otro_navegador_no_autentica(app_login):
    victima = app_login.test_client()
    ajeno = campos(victima.get("/auth/login"))["csrf_token"]["value"]
    atacante = app_login.test_client()
    atacante.get("/auth/login")
    response = atacante.post(
        "/auth/login", data={"csrf_token": ajeno, "email": EMAIL, "password": PASSWORD}
    )
    assert response.status_code == 400
    with app_login.app_context():
        assert db.session.scalars(select(Sesion)).all() == []


def test_csrf_vencido_no_autentica(app_login):
    app_login.config["WTF_CSRF_TIME_LIMIT"] = -1
    response = ingresar(app_login.test_client())
    assert response.status_code == 400
    with app_login.app_context():
        assert db.session.scalars(select(Sesion)).all() == []


def test_logout_requiere_post_csrf_y_revoca_copias_de_la_cookie(app_login):
    cliente = app_login.test_client()
    assert ingresar(cliente).status_code == 303
    cookie_anterior = sesion_cookie(app_login, cliente)
    assert cliente.get("/auth/logout").status_code == 405
    assert cliente.post("/auth/logout").status_code == 400
    assert "Sesión iniciada como" in cliente.get("/").get_data(as_text=True)
    token = campos(cliente.get("/"))["csrf_token"]["value"]
    response = cliente.post("/auth/logout", data={"csrf_token": token})
    assert response.status_code == 303
    assert "Sesión iniciada como" not in cliente.get("/").get_data(as_text=True)
    copia = app_login.test_client()
    copia.set_cookie(app_login.config["SESSION_COOKIE_NAME"], cookie_anterior)
    assert "Sesión iniciada como" not in copia.get("/").get_data(as_text=True)
    with app_login.app_context():
        assert not db.session.scalar(select(Sesion)).activa


def test_login_rota_sesion_y_csrf_e_invalida_la_anterior(app_login):
    cliente = app_login.test_client()
    token_previo = campos(cliente.get("/auth/login"))["csrf_token"]["value"]
    assert ingresar(cliente).status_code == 303
    assert cliente.post("/auth/logout", data={"csrf_token": token_previo}).status_code == 400
    cookie_anterior = sesion_cookie(app_login, cliente)
    assert ingresar(cliente).status_code == 303
    assert sesion_cookie(app_login, cliente) != cookie_anterior
    copia = app_login.test_client()
    copia.set_cookie(app_login.config["SESSION_COOKIE_NAME"], cookie_anterior)
    assert "Sesión iniciada como" not in copia.get("/").get_data(as_text=True)
    with app_login.app_context():
        sesiones = db.session.scalars(select(Sesion)).all()
        assert len(sesiones) == 2
        assert sum(s.activa for s in sesiones) == 1


@pytest.mark.parametrize(
    "motivo", ["vencimiento", "inactividad", "revocacion", "usuario_eliminado"]
)
def test_sesion_se_valida_en_la_base_en_cada_solicitud(app_login, motivo):
    cliente = app_login.test_client()
    assert ingresar(cliente).status_code == 303
    with app_login.app_context():
        sesion = db.session.scalar(select(Sesion))
        if motivo == "vencimiento":
            sesion.fecha_vencimiento = ahora_utc() - timedelta(seconds=1)
        elif motivo == "inactividad":
            sesion.ultimo_acceso = ahora_utc() - timedelta(minutes=31)
        elif motivo == "revocacion":
            sesion.activa = False
        else:
            db.session.execute(delete(Usuario).where(Usuario.id == sesion.usuario_id))
        db.session.commit()
    response = cliente.get("/")
    assert response.status_code == 200
    assert "Sesión iniciada como" not in response.get_data(as_text=True)
    with cliente.session_transaction() as estado:
        assert "auth_token" not in estado


@pytest.mark.parametrize("ataque", ["firma", "token_desconocido", "id_usuario", "token_malformado"])
def test_cookies_manipuladas_no_autentican(app_login, ataque):
    cliente = app_login.test_client()
    if ataque == "firma":
        assert ingresar(cliente).status_code == 303
        cookie = sesion_cookie(app_login, cliente)
        cliente.set_cookie(app_login.config["SESSION_COOKIE_NAME"], cookie + "alterada")
    else:
        with cliente.session_transaction() as estado:
            if ataque == "token_desconocido":
                estado["auth_token"] = secrets.token_urlsafe(32)
            elif ataque == "token_malformado":
                estado["auth_token"] = {"usuario_id": 1}
            else:
                estado["user_id"] = 1
    assert "Sesión iniciada como" not in cliente.get("/").get_data(as_text=True)


def test_sesiones_de_distintos_navegadores_son_independientes(app_login):
    primero, segundo = app_login.test_client(), app_login.test_client()
    assert ingresar(primero).status_code == 303
    assert ingresar(segundo).status_code == 303
    token = campos(primero.get("/"))["csrf_token"]["value"]
    assert primero.post("/auth/logout", data={"csrf_token": token}).status_code == 303
    assert "Sesión iniciada como" in segundo.get("/").get_data(as_text=True)


def test_error_escapa_correo_y_no_repite_contrasena(app_login):
    response = ingresar(app_login.test_client(), email='"><script>alert(1)</script>')
    html = response.get_data(as_text=True)
    assert response.status_code == 401
    assert "<script>" not in html
    assert PASSWORD not in html
    assert "value" not in campos(response)["password"]


def test_nombre_del_usuario_se_escapa_en_inicio(app_login):
    with app_login.app_context():
        usuario = db.session.scalar(select(Usuario))
        usuario.username = "<script>alert(1)</script>"
        db.session.commit()
    cliente = app_login.test_client()
    assert ingresar(cliente).status_code == 303
    html = cliente.get("/").get_data(as_text=True)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_parametro_next_no_redirige_a_sitios_externos(app_login):
    cliente = app_login.test_client()
    token = campos(cliente.get("/auth/login"))["csrf_token"]["value"]
    response = cliente.post(
        "/auth/login?next=https://ejemplo-ajeno.invalid",
        data={"email": EMAIL, "password": PASSWORD, "csrf_token": token},
    )
    assert response.status_code == 303
    assert response.headers["Location"] == "/"


def test_limite_por_cuenta_persiste_entre_cookies_y_direcciones(app_login):
    app_login.config["AUTH_LOGIN_EMAIL_LIMIT"] = 2
    for ip in ["192.0.2.1", "192.0.2.2"]:
        assert ingresar(app_login.test_client(), password="incorrecta", ip=ip).status_code == 401
    response = ingresar(app_login.test_client(), email=" MATI@EJEMPLO.COM ", ip="192.0.2.3")
    assert response.status_code == 429
    assert 0 < int(response.headers["Retry-After"]) <= 900
    with app_login.app_context():
        assert db.session.scalars(select(Sesion)).all() == []
        for contador in db.session.scalars(select(LimiteIntentos)):
            assert len(contador.clave) == 64
            assert EMAIL not in contador.clave
        db.session.execute(
            update(LimiteIntentos).values(inicio_ventana=ahora_utc() - timedelta(minutes=16))
        )
        db.session.commit()
    assert ingresar(app_login.test_client()).status_code == 303


def test_limite_ip_no_se_evade_cambiando_correo_cookie_o_forwarded_for(app_login):
    app_login.config["AUTH_LOGIN_IP_LIMIT"] = 2
    for numero in range(2):
        response = ingresar(
            app_login.test_client(),
            email=f"nadie{numero}@ejemplo.com",
            headers={"X-Forwarded-For": f"192.0.2.{numero + 1}"},
        )
        assert response.status_code == 401
    assert ingresar(app_login.test_client()).status_code == 429


def test_limites_son_compartidos_entre_instancias(app_login):
    app_login.config["AUTH_LOGIN_EMAIL_LIMIT"] = 1
    assert ingresar(app_login.test_client(), password="incorrecta").status_code == 401
    otro = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": SECRET,
            "SQLALCHEMY_DATABASE_URI": app_login.config["SQLALCHEMY_DATABASE_URI"],
            "AUTH_LOGIN_EMAIL_LIMIT": 1,
        }
    )
    assert ingresar(otro.test_client()).status_code == 429
    with otro.app_context():
        db.engine.dispose()


def test_limite_ip_es_atomico_con_solicitudes_concurrentes(app_login):
    app_login.config["AUTH_LOGIN_IP_LIMIT"] = 3

    def intento(numero):
        return ingresar(app_login.test_client(), email=f"nadie{numero}@ejemplo.com").status_code

    with ThreadPoolExecutor(max_workers=4) as executor:
        resultados = list(executor.map(intento, range(8)))
    assert resultados.count(401) == 3
    assert resultados.count(429) == 5


def test_registro_tambien_limita_intentos(app_login):
    app_login.config["AUTH_REGISTER_IP_LIMIT"] = 1
    cliente = app_login.test_client()
    for esperado in [400, 429]:
        token = campos(cliente.get("/auth/register"))["csrf_token"]["value"]
        response = cliente.post(
            "/auth/register",
            data={"csrf_token": token, "email": EMAIL, "username": "Mati", "password": PASSWORD},
        )
        assert response.status_code == esperado


@pytest.mark.parametrize("ruta", ["/auth/login", "/auth/register"])
def test_rechaza_formularios_demasiado_grandes_antes_del_hash(app_login, ruta):
    cliente = app_login.test_client()
    token = campos(cliente.get(ruta))["csrf_token"]["value"]
    response = cliente.post(
        ruta, data={"csrf_token": token, "email": EMAIL, "password": "x" * (17 * 1024)}
    )
    assert response.status_code == 413
    with app_login.app_context():
        assert db.session.scalars(select(Sesion)).all() == []


def test_respuestas_no_se_cachean_y_llevan_cabeceras_de_proteccion(app_login):
    response = app_login.test_client().get("/auth/login")
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "form-action 'self'" in response.headers["Content-Security-Policy"]


def test_produccion_exige_https_hosts_y_cookie_secure(app_login, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("TRUSTED_HOSTS", "localhost")
    monkeypatch.setenv("SECRET_KEY", SECRET)
    app = create_app(
        {"TESTING": True, "SQLALCHEMY_DATABASE_URI": app_login.config["SQLALCHEMY_DATABASE_URI"]}
    )
    cliente = app.test_client()
    assert cliente.get("/auth/login").status_code == 400
    assert cliente.get("/auth/login", headers={"X-Forwarded-Proto": "https"}).status_code == 400
    assert cliente.get("/auth/login", base_url="https://host-ajeno.invalid").status_code == 400
    response = cliente.get("/auth/login", base_url="https://localhost")
    assert response.status_code == 200
    assert "max-age=" in response.headers["Strict-Transport-Security"]
    token = campos(response)["csrf_token"]["value"]
    response = cliente.post(
        "/auth/login",
        base_url="https://localhost",
        headers={"Referer": "https://localhost/auth/login"},
        data={"email": EMAIL, "password": PASSWORD, "csrf_token": token},
    )
    assert response.status_code == 303
    cookie = response.headers["Set-Cookie"]
    assert cookie.startswith("__Host-compilando=")
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert "Domain=" not in cookie
    with app.app_context():
        db.engine.dispose()


@pytest.mark.parametrize(
    "defecto",
    ["clave_ausente", "clave_corta", "hosts", "debug", "cookie", "http_only", "same_site"],
)
def test_produccion_rechaza_configuracion_insegura(monkeypatch, defecto):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("TRUSTED_HOSTS", "localhost")
    monkeypatch.setenv("SECRET_KEY", SECRET)
    config = {"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"}
    if defecto == "clave_ausente":
        monkeypatch.delenv("SECRET_KEY")
    elif defecto == "clave_corta":
        monkeypatch.setenv("SECRET_KEY", "corta")
    elif defecto == "hosts":
        monkeypatch.delenv("TRUSTED_HOSTS")
    elif defecto == "debug":
        config["DEBUG"] = True
    elif defecto == "cookie":
        config["SESSION_COOKIE_SECURE"] = False
    elif defecto == "http_only":
        config["SESSION_COOKIE_HTTPONLY"] = False
    else:
        config["SESSION_COOKIE_SAMESITE"] = None
    with pytest.raises(RuntimeError):
        create_app(config)


def test_health_sigue_funcionando_sin_consultar_la_base_aunque_haya_cookie():
    app = create_app(
        {"TESTING": True, "SECRET_KEY": SECRET, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"}
    )
    cliente = app.test_client()
    with cliente.session_transaction() as estado:
        estado["auth_token"] = secrets.token_urlsafe(32)
    assert cliente.get("/health").json["status"] == "ok"


def test_nombre_de_entorno_incorrecto_no_activa_desarrollo_silenciosamente(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    with pytest.raises(RuntimeError, match="APP_ENV"):
        create_app({"TESTING": True})


def test_migracion_de_sesiones_se_puede_revertir_sin_borrar_usuarios(app_login):
    with app_login.app_context():
        downgrade(revision="bb57280189ce")
        assert "sesiones" not in inspect(db.engine).get_table_names()
        assert "limites_autenticacion" not in inspect(db.engine).get_table_names()
        assert db.session.scalar(select(Usuario.email)) == EMAIL
        db.session.remove()
        upgrade()
        assert "sesiones" in inspect(db.engine).get_table_names()
        assert db.session.scalar(select(Usuario.email)) == EMAIL


@pytest.fixture
def app_con_rutas_privadas(app_login):
    """Estas vistas existen solo en las pruebas; no se agregan rutas al producto."""
    ejecuciones = []

    @app_login.route("/privada/<int:recurso_id>", methods=["GET", "POST"])
    @requiere_sesion
    def privada(recurso_id):
        ejecuciones.append((recurso_id, g.usuario_actual.id, request.method))
        return {"recurso_id": recurso_id, "usuario_id": g.usuario_actual.id}

    @app_login.get("/otra-privada")
    @requiere_sesion
    def otra_privada():
        ejecuciones.append((None, g.usuario_actual.id, request.method))
        return {"usuario_id": g.usuario_actual.id}

    return app_login, ejecuciones


@pytest.mark.parametrize("metodo", ["GET", "HEAD"])
def test_ruta_privada_sin_sesion_pide_login_sin_ejecutar_la_vista(app_con_rutas_privadas, metodo):
    app, ejecuciones = app_con_rutas_privadas
    response = app.test_client().open("/privada/7", method=metodo)
    assert response.status_code == 303
    assert response.headers["Location"] == "/auth/login"
    assert response.headers["Cache-Control"] == "no-store"
    assert ejecuciones == []


def test_rutas_privadas_permiten_sesion_valida_y_conservan_sus_argumentos(app_con_rutas_privadas):
    app, ejecuciones = app_con_rutas_privadas
    cliente = app.test_client()
    assert ingresar(cliente).status_code == 303
    with app.app_context():
        usuario_id = db.session.scalar(select(Usuario.id).where(Usuario.email == EMAIL))
    assert cliente.get("/privada/17").json == {"recurso_id": 17, "usuario_id": usuario_id}
    assert cliente.get("/otra-privada").json == {"usuario_id": usuario_id}
    assert ejecuciones == [(17, usuario_id, "GET"), (None, usuario_id, "GET")]


@pytest.mark.parametrize(
    "motivo",
    [
        "vencimiento",
        "inactividad",
        "revocacion",
        "sesion_inexistente",
        "usuario_eliminado",
        "cookie",
    ],
)
def test_ruta_privada_rechaza_sesion_invalida_sin_ejecutar_la_vista(app_con_rutas_privadas, motivo):
    app, ejecuciones = app_con_rutas_privadas
    cliente = app.test_client()
    assert ingresar(cliente).status_code == 303
    if motivo == "cookie":
        cliente.set_cookie(
            app.config["SESSION_COOKIE_NAME"], sesion_cookie(app, cliente) + "alterada"
        )
    else:
        with app.app_context():
            sesion = db.session.scalar(select(Sesion))
            if motivo == "vencimiento":
                sesion.fecha_vencimiento = ahora_utc() - timedelta(seconds=1)
            elif motivo == "inactividad":
                sesion.ultimo_acceso = ahora_utc() - timedelta(minutes=31)
            elif motivo == "revocacion":
                sesion.activa = False
            elif motivo == "sesion_inexistente":
                db.session.delete(sesion)
            else:
                db.session.execute(delete(Usuario).where(Usuario.id == sesion.usuario_id))
            db.session.commit()

    response = cliente.get("/privada/7")
    assert response.status_code == 303
    assert response.headers["Location"] == "/auth/login"
    assert ejecuciones == []
    with cliente.session_transaction() as estado:
        assert "auth_token" not in estado


def test_logout_impide_reusar_la_cookie_en_rutas_privadas(app_con_rutas_privadas):
    app, ejecuciones = app_con_rutas_privadas
    cliente = app.test_client()
    assert ingresar(cliente).status_code == 303
    assert cliente.get("/privada/7").status_code == 200
    cookie_anterior = sesion_cookie(app, cliente)
    csrf = campos(cliente.get("/"))["csrf_token"]["value"]
    assert cliente.post("/auth/logout", data={"csrf_token": csrf}).status_code == 303

    copia = app.test_client()
    copia.set_cookie(app.config["SESSION_COOKIE_NAME"], cookie_anterior)
    assert copia.get("/privada/7").status_code == 303
    assert cliente.get("/privada/7").status_code == 303
    assert len(ejecuciones) == 1

    assert ingresar(cliente).status_code == 303
    assert cliente.get("/privada/7").status_code == 200
    assert len(ejecuciones) == 2


def test_post_privado_requiere_sesion_aunque_el_csrf_sea_valido(app_con_rutas_privadas):
    app, ejecuciones = app_con_rutas_privadas
    cliente = app.test_client()
    csrf = campos(cliente.get("/auth/login"))["csrf_token"]["value"]
    response = cliente.post("/privada/7", data={"csrf_token": csrf, "usuario_id": 1})
    assert response.status_code == 303
    assert response.headers["Location"] == "/auth/login"
    assert ejecuciones == []


def test_post_privado_requiere_csrf_ademas_de_sesion_valida(app_con_rutas_privadas):
    app, ejecuciones = app_con_rutas_privadas
    cliente = app.test_client()
    assert ingresar(cliente).status_code == 303
    assert cliente.post("/privada/7").status_code == 400
    assert ejecuciones == []

    csrf = campos(cliente.get("/"))["csrf_token"]["value"]
    response = cliente.post("/privada/7", data={"csrf_token": csrf})
    assert response.status_code == 200
    assert ejecuciones == [(7, response.json["usuario_id"], "POST")]


def test_redireccion_al_login_no_copia_parametros_de_la_peticion_privada(app_con_rutas_privadas):
    app, ejecuciones = app_con_rutas_privadas
    response = app.test_client().get("/privada/7?next=https://ajeno.invalid&dato=privado")
    assert response.status_code == 303
    assert response.headers["Location"] == "/auth/login"
    assert ejecuciones == []


def test_pedir_login_permite_reingresar_y_luego_acceder_a_la_ruta_privada(app_con_rutas_privadas):
    app, ejecuciones = app_con_rutas_privadas
    cliente = app.test_client()
    response = cliente.get("/privada/7", follow_redirects=True)
    assert response.status_code == 200
    assert "Iniciar sesión" in response.get_data(as_text=True)
    assert ejecuciones == []
    assert ingresar(cliente).status_code == 303
    assert cliente.get("/privada/7").status_code == 200


@pytest.mark.parametrize("ruta", ["/", "/auth/login", "/auth/register", "/health"])
def test_proteccion_de_rutas_privadas_conserva_el_acceso_a_las_publicas(
    app_con_rutas_privadas, ruta
):
    app, ejecuciones = app_con_rutas_privadas
    assert app.test_client().get(ruta).status_code == 200
    assert ejecuciones == []
