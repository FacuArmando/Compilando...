"""Cambio de correo con CSRF, credenciales, sesiones y concurrencia reales."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from html.parser import HTMLParser
from threading import Barrier
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import event, select
from werkzeug.security import check_password_hash, generate_password_hash

from compilando import create_app
from compilando.extensions import db
from compilando.modules.answers.models import Respuesta
from compilando.modules.answers.services import publicar_respuesta
from compilando.modules.auth.models import Sesion, Usuario
from compilando.modules.auth.services import cambiar_email, registrar_usuario
from compilando.modules.auth.sessions import ahora_utc
from compilando.modules.questions.models import Pregunta
from compilando.modules.questions.services import publicar_pregunta

EMAIL = "mati@ejemplo.com"
NUEVO = "nuevo@ejemplo.com"
OTRO = "otra@ejemplo.com"
PASSWORD = "clave-prueba"
RUTA = "/auth/account/email"


@pytest.fixture
def app_email(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "clave-exclusiva-de-pruebas-de-cambio-de-correo-123456789",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'email.sqlite'}",
        }
    )
    with app.app_context():
        db.create_all()
        registrar_usuario("Mati", EMAIL, PASSWORD)
        registrar_usuario("Otra persona", OTRO, PASSWORD)
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


class Campos(HTMLParser):
    def __init__(self, response):
        super().__init__()
        self.campos = {}
        self.feed(response.get_data(as_text=True))

    def handle_starttag(self, tag, attrs):
        atributos = dict(attrs)
        if tag == "input":
            self.campos[atributos["name"]] = atributos


def csrf(response):
    return Campos(response).campos["csrf_token"]["value"]


def ingresar(cliente, email=EMAIL, password=PASSWORD):
    return cliente.post(
        "/auth/login",
        data={
            "csrf_token": csrf(cliente.get("/auth/login")),
            "email": email,
            "password": password,
        },
    )


@pytest.fixture
def cliente_email(app_email):
    cliente = app_email.test_client()
    assert ingresar(cliente).status_code == 303
    return cliente


def datos(token, nuevo=NUEVO, actual=PASSWORD):
    return {"csrf_token": token, "email_nuevo": nuevo, "email_password_actual": actual}


def test_formulario_muestra_correo_actual_y_pide_confirmar_password(cliente_email):
    response = cliente_email.get("/auth/account")
    html = response.get_data(as_text=True)
    campos = Campos(response).campos
    assert f'action="{RUTA}"' in html and EMAIL in html
    assert campos["email_nuevo"]["type"] == "email"
    assert campos["email_nuevo"]["maxlength"] == "254"
    assert campos["email_password_actual"]["type"] == "password"
    assert campos["email_password_actual"]["maxlength"] == "128"
    assert "value" not in campos["email_password_actual"]
    assert "correo nuevo y la misma contraseña" in html


def test_cambio_normaliza_correo_conserva_cuenta_y_exige_nuevo_login(app_email, cliente_email):
    with app_email.app_context():
        usuario = db.session.scalar(select(Usuario).where(Usuario.email == EMAIL))
        usuario_id, hash_original = usuario.id, usuario.password_hash
        pregunta = publicar_pregunta(
            "Una pregunta de prueba", "¿Cómo funciona una interfaz?", "Python", ["Flask"], usuario
        )
        pregunta_id = pregunta.id
        respuesta_id = publicar_respuesta(
            pregunta.id, "Una respuesta propia de prueba.", usuario
        ).id
    otro_navegador = app_email.test_client()
    assert ingresar(otro_navegador).status_code == 303
    otra_cuenta = app_email.test_client()
    assert ingresar(otra_cuenta, email=OTRO).status_code == 303
    cookie = cliente_email.get_cookie(app_email.config["SESSION_COOKIE_NAME"]).value
    token = csrf(cliente_email.get("/auth/account"))
    response = cliente_email.post(RUTA, data=datos(token, nuevo="  NUEVO@EJEMPLO.COM  "))
    assert response.status_code == 303
    destino = urlsplit(response.headers["Location"])
    assert destino.path == "/auth/login"
    assert parse_qs(destino.query)["next"] == ["/auth/account"]
    with cliente_email.session_transaction() as estado:
        assert "auth_token" not in estado and "csrf_token" not in estado
    with app_email.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        assert usuario.email == NUEVO and usuario.username == "Mati"
        assert usuario.password_hash == hash_original
        assert check_password_hash(usuario.password_hash, PASSWORD)
        assert len(db.session.scalars(select(Usuario)).all()) == 2
        assert db.session.get(Pregunta, pregunta_id).usuario_id == usuario_id
        assert db.session.get(Respuesta, respuesta_id).usuario_id == usuario_id
        assert all(
            not sesion.activa
            for sesion in db.session.scalars(select(Sesion).where(Sesion.usuario_id == usuario_id))
        )
    copia_cookie = app_email.test_client()
    copia_cookie.set_cookie(app_email.config["SESSION_COOKIE_NAME"], cookie)
    assert copia_cookie.get("/auth/account").status_code == 303
    assert otro_navegador.get("/auth/account").status_code == 303
    assert otra_cuenta.get("/auth/account").status_code == 200
    login = cliente_email.get(response.headers["Location"])
    assert "Tu correo se actualizó." in login.get_data(as_text=True)
    assert PASSWORD not in login.get_data(as_text=True)
    assert ingresar(app_email.test_client(), email=EMAIL).status_code == 401
    assert ingresar(cliente_email, email=NUEVO).status_code == 303
    assert NUEVO in cliente_email.get("/auth/account").get_data(as_text=True)


@pytest.mark.parametrize(
    ("nuevo", "actual", "mensaje"),
    [
        ("", PASSWORD, "Completá"),
        ("   ", PASSWORD, "Completá"),
        (NUEVO, "", "Completá"),
        (NUEVO, "incorrecta", "actual no es correcta"),
        (NUEVO, "x" * 129, "actual no es correcta"),
        ("sin-arroba", PASSWORD, "correo electrónico válido"),
        ("@ejemplo.com", PASSWORD, "correo electrónico válido"),
        ("mati@", PASSWORD, "correo electrónico válido"),
        ("mati@ejemplo", PASSWORD, "correo electrónico válido"),
        ("ma ti@ejemplo.com", PASSWORD, "correo electrónico válido"),
        ("mati@@ejemplo.com", PASSWORD, "correo electrónico válido"),
        ("m" * 243 + "@ejemplo.com", PASSWORD, "correo electrónico válido"),
        ("  MATI@EJEMPLO.COM ", PASSWORD, "diferente del actual"),
        ("  OTRA@EJEMPLO.COM ", PASSWORD, "ya está registrado"),
    ],
)
def test_cambio_invalido_conserva_correo_password_y_sesion(
    app_email, cliente_email, nuevo, actual, mensaje
):
    with app_email.app_context():
        usuario = db.session.scalar(select(Usuario).where(Usuario.email == EMAIL))
        usuario_id, hash_original = usuario.id, usuario.password_hash
    response = cliente_email.post(
        RUTA, data=datos(csrf(cliente_email.get("/auth/account")), nuevo, actual)
    )
    assert response.status_code == 400
    assert mensaje in response.get_data(as_text=True)
    assert Campos(response).campos["email_nuevo"]["value"] == nuevo[:254]
    assert "value" not in Campos(response).campos["email_password_actual"]
    assert PASSWORD not in response.get_data(as_text=True)
    with app_email.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        assert usuario.email == EMAIL and usuario.password_hash == hash_original
        assert db.session.scalar(select(Sesion)).activa


def test_duplicado_solo_se_informa_despues_de_comprobar_password(cliente_email):
    token = csrf(cliente_email.get("/auth/account"))
    response = cliente_email.post(RUTA, data=datos(token, OTRO, "incorrecta"))
    assert response.status_code == 400
    assert "actual no es correcta" in response.get_data(as_text=True)
    assert "ya está registrado" not in response.get_data(as_text=True)


def test_correo_rechazado_se_escapa_en_el_html(cliente_email):
    nuevo = '"><script>alert(1)</script>'
    response = cliente_email.post(RUTA, data=datos(csrf(cliente_email.get("/auth/account")), nuevo))
    assert response.status_code == 400
    assert nuevo not in response.get_data(as_text=True)
    assert Campos(response).campos["email_nuevo"]["value"] == nuevo


@pytest.mark.parametrize("modo", ["ausente", "incorrecto", "ajeno", "vencido"])
def test_csrf_invalido_no_cambia_el_correo(app_email, cliente_email, modo):
    token = csrf(cliente_email.get("/auth/account"))
    if modo == "incorrecto":
        token = "incorrecto"
    elif modo == "ajeno":
        token = csrf(app_email.test_client().get("/auth/login"))
    elif modo == "vencido":
        app_email.config["WTF_CSRF_TIME_LIMIT"] = -1
    envio = datos(token)
    if modo == "ausente":
        del envio["csrf_token"]
    response = cliente_email.post(RUTA, data=envio)
    assert response.status_code == 400
    assert "El formulario venció o no es válido." in response.get_data(as_text=True)
    assert Campos(response).campos["email_nuevo"]["value"] == NUEVO
    assert "value" not in Campos(response).campos["email_password_actual"]
    with app_email.app_context():
        assert db.session.scalar(select(Usuario).where(Usuario.email == EMAIL)) is not None
        assert db.session.scalar(select(Sesion)).activa


@pytest.mark.parametrize(
    "motivo", ["anonimo", "vencimiento", "inactividad", "revocacion", "cookie"]
)
def test_sesion_invalida_impide_cambiar_el_correo(app_email, motivo):
    cliente = app_email.test_client()
    if motivo != "anonimo":
        assert ingresar(cliente).status_code == 303
        token = csrf(cliente.get("/auth/account"))
        if motivo == "cookie":
            cookie = cliente.get_cookie(app_email.config["SESSION_COOKIE_NAME"]).value
            cliente.set_cookie(app_email.config["SESSION_COOKIE_NAME"], cookie + "alterada")
        else:
            with app_email.app_context():
                sesion = db.session.scalar(select(Sesion))
                if motivo == "vencimiento":
                    sesion.fecha_vencimiento = ahora_utc() - timedelta(seconds=1)
                elif motivo == "inactividad":
                    sesion.ultimo_acceso = ahora_utc() - timedelta(minutes=31)
                else:
                    sesion.activa = False
                db.session.commit()
    else:
        token = csrf(cliente.get("/auth/login"))
    response = cliente.post(RUTA, data=datos(token))
    assert response.status_code == 303
    assert urlsplit(response.headers["Location"]).path == "/auth/login"
    assert EMAIL not in response.get_data(as_text=True)
    with app_email.app_context():
        assert db.session.scalar(select(Usuario).where(Usuario.email == EMAIL)) is not None


def test_campos_ajenos_no_deciden_que_cuenta_se_modifica(app_email, cliente_email):
    with app_email.app_context():
        otro = db.session.scalar(select(Usuario).where(Usuario.email == OTRO))
        otro_id, hash_ajeno = otro.id, otro.password_hash
    envio = datos(csrf(cliente_email.get("/auth/account")))
    envio.update({"usuario_id": otro_id, "email": OTRO, "username": "Otro nombre"})
    response = cliente_email.post(f"{RUTA}?usuario_id={otro_id}", data=envio)
    assert response.status_code == 303
    with app_email.app_context():
        otro = db.session.get(Usuario, otro_id)
        assert otro.email == OTRO and otro.password_hash == hash_ajeno
        assert db.session.scalar(select(Usuario).where(Usuario.email == NUEVO)).username == "Mati"


def test_cambios_de_correo_y_password_comparten_limite_por_cuenta(app_email, cliente_email):
    app_email.config["AUTH_PASSWORD_ACCOUNT_LIMIT"] = 2
    token = csrf(cliente_email.get("/auth/account"))
    response = cliente_email.post(
        "/auth/account/password",
        data={
            "csrf_token": token,
            "password_actual": "incorrecta",
            "password_nueva": "otra-clave",
            "password_confirmacion": "otra-clave",
        },
        environ_overrides={"REMOTE_ADDR": "192.0.2.1"},
    )
    assert response.status_code == 400
    assert (
        cliente_email.post(
            RUTA,
            data=datos(token, actual="incorrecta"),
            environ_overrides={"REMOTE_ADDR": "192.0.2.2"},
        ).status_code
        == 400
    )
    limitado = cliente_email.post(
        RUTA, data=datos(token), environ_overrides={"REMOTE_ADDR": "192.0.2.3"}
    )
    assert limitado.status_code == 429
    assert 0 < int(limitado.headers["Retry-After"]) <= 900
    assert "Hubo demasiados intentos" in limitado.get_data(as_text=True)
    assert "value" not in Campos(limitado).campos["email_password_actual"]
    with app_email.app_context():
        assert db.session.scalar(select(Usuario).where(Usuario.email == EMAIL)) is not None
        assert db.session.scalar(select(Sesion)).activa


def test_limite_por_ip_impide_reintentar_con_otra_cuenta(app_email, cliente_email):
    app_email.config["AUTH_PASSWORD_IP_LIMIT"] = 1
    token = csrf(cliente_email.get("/auth/account"))
    assert cliente_email.post(RUTA, data=datos(token, actual="incorrecta")).status_code == 400
    otro = app_email.test_client()
    assert ingresar(otro, email=OTRO).status_code == 303
    token_ajeno = csrf(otro.get("/auth/account"))
    limitado = otro.post(RUTA, data=datos(token_ajeno))
    assert limitado.status_code == 429
    with app_email.app_context():
        assert db.session.scalar(select(Usuario).where(Usuario.email == OTRO)) is not None


def test_password_anterior_larga_sigue_sirviendo_para_cambiar_correo(app_email):
    anterior = "password-anterior-de-una-cuenta-legada"
    with app_email.app_context():
        usuario = db.session.scalar(select(Usuario).where(Usuario.email == EMAIL))
        usuario.password_hash = generate_password_hash(anterior)
        db.session.commit()
    cliente = app_email.test_client()
    assert ingresar(cliente, password=anterior).status_code == 303
    token = csrf(cliente.get("/auth/account"))
    assert cliente.post(RUTA, data=datos(token, actual=anterior)).status_code == 303
    assert ingresar(app_email.test_client(), email=NUEVO, password=anterior).status_code == 303


def test_fallo_de_guardado_revierte_correo_y_revocaciones(app_email, cliente_email, monkeypatch):
    def fallo():
        raise RuntimeError("Fallo simulado de persistencia")

    with app_email.app_context():
        usuario = db.session.scalar(select(Usuario).where(Usuario.email == EMAIL))
        usuario_id, hash_original = usuario.id, usuario.password_hash
        monkeypatch.setattr(db.session, "commit", fallo)
        with pytest.raises(RuntimeError, match="Fallo simulado"):
            cambiar_email(usuario, NUEVO, PASSWORD)
        usuario = db.session.get(Usuario, usuario_id)
        assert usuario.email == EMAIL and usuario.password_hash == hash_original
        assert db.session.scalar(select(Sesion)).activa


@pytest.mark.parametrize("modo", ["mismo_correo", "misma_cuenta"])
def test_cambios_simultaneos_respetan_unicidad_y_no_se_sobrescriben(app_email, modo):
    barrera = Barrier(2)
    with app_email.app_context():
        engine = db.engine
        usuarios = db.session.scalars(select(Usuario).order_by(Usuario.id)).all()
        ids = [usuario.id for usuario in usuarios]

    def esperar_antes_de_actualizar(connection, cursor, statement, parameters, context, many):
        if statement.startswith("UPDATE usuarios SET email="):
            barrera.wait(timeout=10)

    def intentar(cambio):
        usuario_id, nuevo = cambio
        with app_email.app_context():
            usuario = db.session.get(Usuario, usuario_id)
            try:
                cambiar_email(usuario, nuevo, PASSWORD)
            except ValueError as error:
                return str(error)
            return "actualizado"

    cambios = [(ids[0], NUEVO), (ids[1], NUEVO)]
    if modo == "misma_cuenta":
        cambios = [(ids[0], NUEVO), (ids[0], "distinto@ejemplo.com")]
    event.listen(engine, "before_cursor_execute", esperar_antes_de_actualizar)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(intentar, cambios))
    finally:
        event.remove(engine, "before_cursor_execute", esperar_antes_de_actualizar)
    assert resultados.count("actualizado") == 1
    mensaje = "ya está registrado" if modo == "mismo_correo" else "tu cuenta cambiaron"
    assert any(mensaje in resultado for resultado in resultados)
    with app_email.app_context():
        correos = db.session.scalars(select(Usuario.email)).all()
        assert len(correos) == len(set(correos)) == 2
