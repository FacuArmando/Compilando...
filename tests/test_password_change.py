"""Cambio de contraseña con sesiones reales, CSRF y bases temporales."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from html.parser import HTMLParser
from threading import Barrier
from urllib.parse import urlsplit

import pytest
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from compilando import create_app
from compilando.extensions import db
from compilando.modules.auth import services
from compilando.modules.auth.models import Sesion, Usuario
from compilando.modules.auth.services import registrar_usuario
from compilando.modules.auth.sessions import ahora_utc

ACTUAL = "clave-prueba"
NUEVA = "nueva-clave"
EMAIL = "mati@ejemplo.com"
RUTA = "/auth/account/password"


@pytest.fixture
def app_password(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "clave-exclusiva-de-pruebas-de-cambio-de-contrasena-123456",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'password.sqlite'}",
        }
    )
    with app.app_context():
        db.create_all()
        registrar_usuario("Mati", EMAIL, ACTUAL)
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
        attrs = dict(attrs)
        if tag == "input":
            self.campos[attrs["name"]] = attrs


def csrf(response):
    return Campos(response).campos["csrf_token"]["value"]


def ingresar(cliente, email=EMAIL, password=ACTUAL):
    return cliente.post(
        "/auth/login",
        data={
            "csrf_token": csrf(cliente.get("/auth/login")),
            "email": email,
            "password": password,
        },
    )


@pytest.fixture
def cliente_password(app_password):
    cliente = app_password.test_client()
    assert ingresar(cliente).status_code == 303
    return cliente


def datos(token, actual=ACTUAL, nueva=NUEVA, confirmacion=NUEVA):
    return {
        "csrf_token": token,
        "password_actual": actual,
        "password_nueva": nueva,
        "password_confirmacion": confirmacion,
    }


def test_mi_cuenta_ofrece_cambio_sin_exponer_contrasenas(cliente_password):
    response = cliente_password.get("/auth/account")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert f'action="{RUTA}"' in html
    assert "se cerrarán todas tus sesiones" in html
    campos = Campos(response).campos
    assert campos["password_actual"]["maxlength"] == "128"
    for nombre in ["password_actual", "password_nueva", "password_confirmacion"]:
        assert campos[nombre]["type"] == "password"
        assert "value" not in campos[nombre]
    assert campos["password_nueva"]["minlength"] == "8"
    assert campos["password_nueva"]["pattern"] == r"[\s\S]{8,18}"
    assert "maxlength" not in campos["password_nueva"]
    assert "maxlength" not in campos["password_confirmacion"]


def test_cambio_guarda_hash_revoca_sesiones_y_exige_login_nuevo(app_password, cliente_password):
    otro_navegador = app_password.test_client()
    assert ingresar(otro_navegador).status_code == 303
    cookie = cliente_password.get_cookie(app_password.config["SESSION_COOKIE_NAME"]).value
    formulario = cliente_password.get("/auth/account")
    response = cliente_password.post(RUTA, data=datos(csrf(formulario)))
    assert response.status_code == 303
    assert urlsplit(response.headers["Location"]).path == "/auth/login"
    with cliente_password.session_transaction() as estado:
        assert "auth_token" not in estado
        assert "csrf_token" not in estado
    with app_password.app_context():
        usuario = db.session.scalar(select(Usuario))
        assert usuario.password_hash not in {ACTUAL, NUEVA}
        assert check_password_hash(usuario.password_hash, NUEVA)
        assert not check_password_hash(usuario.password_hash, ACTUAL)
        sesiones = db.session.scalars(select(Sesion)).all()
        assert len(sesiones) == 2
        assert all(not sesion.activa for sesion in sesiones)
    copia_cookie = app_password.test_client()
    copia_cookie.set_cookie(app_password.config["SESSION_COOKIE_NAME"], cookie)
    assert copia_cookie.get("/auth/account").status_code == 303
    assert otro_navegador.get("/auth/account").status_code == 303
    login = cliente_password.get(response.headers["Location"])
    assert "Tu contraseña se actualizó." in login.get_data(as_text=True)
    assert NUEVA not in login.get_data(as_text=True)
    assert ingresar(app_password.test_client(), password=ACTUAL).status_code == 401
    assert ingresar(app_password.test_client(), password=NUEVA).status_code == 303
    assert cliente_password.get("/auth/account").status_code == 303


@pytest.mark.parametrize(
    ("actual", "nueva", "confirmacion", "mensaje"),
    [
        ("", NUEVA, NUEVA, "Completá"),
        (ACTUAL, "", "", "Completá"),
        (ACTUAL, NUEVA, "", "Completá"),
        ("incorrecta", NUEVA, NUEVA, "actual no es correcta"),
        ("x" * 129, NUEVA, NUEVA, "actual no es correcta"),
        (ACTUAL, "x" * 7, "x" * 7, "entre 8 y 18"),
        (ACTUAL, "x" * 19, "x" * 19, "entre 8 y 18"),
        (ACTUAL, " " * 8, " " * 8, "entre 8 y 18"),
        (ACTUAL, NUEVA, "distinta123", "no coinciden"),
        (ACTUAL, ACTUAL, ACTUAL, "diferente de la actual"),
    ],
)
def test_cambio_invalido_no_modifica_hash_ni_revoca_sesion(
    app_password, cliente_password, actual, nueva, confirmacion, mensaje
):
    with app_password.app_context():
        original = db.session.scalar(select(Usuario.password_hash))
    token = csrf(cliente_password.get("/auth/account"))
    response = cliente_password.post(RUTA, data=datos(token, actual, nueva, confirmacion))
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert mensaje in html
    assert 'id="password-error"' in html
    for nombre in ["password_actual", "password_nueva", "password_confirmacion"]:
        assert "value" not in Campos(response).campos[nombre]
    assert ACTUAL not in html and NUEVA not in html
    with app_password.app_context():
        assert db.session.scalar(select(Usuario.password_hash)) == original
        assert db.session.scalar(select(Sesion)).activa


@pytest.mark.parametrize(
    "nueva", ["p" * 8, "p" * 12, "p" * 13, "p" * 18, " nueva123 ", "contraseñá9"]
)
def test_nueva_contrasena_respeta_limites_y_conserva_sus_caracteres(
    app_password, cliente_password, nueva
):
    token = csrf(cliente_password.get("/auth/account"))
    response = cliente_password.post(RUTA, data=datos(token, nueva=nueva, confirmacion=nueva))
    assert response.status_code == 303
    with app_password.app_context():
        guardado = db.session.scalar(select(Usuario.password_hash))
        assert check_password_hash(guardado, nueva)
        if nueva != nueva.strip():
            assert not check_password_hash(guardado, nueva.strip())
    assert ingresar(app_password.test_client(), password=nueva).status_code == 303


def test_cuenta_con_clave_anterior_larga_puede_cambiarla(app_password):
    anterior = "contraseña-anterior-larga-12345"
    with app_password.app_context():
        usuario = db.session.scalar(select(Usuario))
        usuario.password_hash = generate_password_hash(anterior)
        db.session.commit()
    cliente = app_password.test_client()
    assert ingresar(cliente, password=anterior).status_code == 303
    token = csrf(cliente.get("/auth/account"))
    assert cliente.post(RUTA, data=datos(token, actual=anterior)).status_code == 303
    assert ingresar(app_password.test_client(), password=NUEVA).status_code == 303


def test_cambiar_solo_mayusculas_se_guarda_y_login_exige_las_mayusculas(
    app_password, cliente_password
):
    nueva = ACTUAL.upper()
    token = csrf(cliente_password.get("/auth/account"))
    response = cliente_password.post(RUTA, data=datos(token, nueva=nueva, confirmacion=nueva))
    assert response.status_code == 303
    assert ingresar(app_password.test_client(), password=ACTUAL).status_code == 401
    assert ingresar(app_password.test_client(), password=ACTUAL.capitalize()).status_code == 401
    assert ingresar(app_password.test_client(), password=nueva).status_code == 303


@pytest.mark.parametrize("modo", ["ausente", "incorrecto", "ajeno", "vencido"])
def test_cambio_rechaza_csrf_sin_modificar_la_cuenta(app_password, cliente_password, modo):
    token = csrf(cliente_password.get("/auth/account"))
    if modo == "incorrecto":
        token = "incorrecto"
    elif modo == "ajeno":
        token = csrf(app_password.test_client().get("/auth/login"))
    elif modo == "vencido":
        app_password.config["WTF_CSRF_TIME_LIMIT"] = -1
    envio = datos(token)
    if modo == "ausente":
        del envio["csrf_token"]
    response = cliente_password.post(RUTA, data=envio)
    assert response.status_code == 400
    assert "El formulario venció o no es válido." in response.get_data(as_text=True)
    assert NUEVA not in response.get_data(as_text=True)
    with app_password.app_context():
        assert check_password_hash(db.session.scalar(select(Usuario.password_hash)), ACTUAL)
        assert db.session.scalar(select(Sesion)).activa


@pytest.mark.parametrize(
    "motivo", ["anonimo", "vencimiento", "inactividad", "revocacion", "cookie"]
)
def test_sin_sesion_valida_no_se_puede_cambiar_la_contrasena(app_password, motivo):
    cliente = app_password.test_client()
    if motivo != "anonimo":
        assert ingresar(cliente).status_code == 303
        token = csrf(cliente.get("/auth/account"))
        if motivo == "cookie":
            cookie = cliente.get_cookie(app_password.config["SESSION_COOKIE_NAME"]).value
            cliente.set_cookie(app_password.config["SESSION_COOKIE_NAME"], cookie + "alterada")
        else:
            with app_password.app_context():
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
    with app_password.app_context():
        assert check_password_hash(db.session.scalar(select(Usuario.password_hash)), ACTUAL)


def test_cambio_ignora_otras_identidades_y_conserva_las_sesiones_ajenas(
    app_password, cliente_password
):
    with app_password.app_context():
        otro = registrar_usuario("Otra persona", "otra@ejemplo.com", ACTUAL)
        otro_id, hash_ajeno = otro.id, otro.password_hash
    otro_cliente = app_password.test_client()
    assert ingresar(otro_cliente, email="otra@ejemplo.com").status_code == 303
    envio = datos(csrf(cliente_password.get("/auth/account")))
    envio.update({"usuario_id": otro_id, "email": "otra@ejemplo.com"})
    response = cliente_password.post(f"{RUTA}?usuario_id={otro_id}", data=envio)
    assert response.status_code == 303
    assert otro_cliente.get("/auth/account").status_code == 200
    with app_password.app_context():
        assert db.session.get(Usuario, otro_id).password_hash == hash_ajeno
        propio = db.session.scalar(select(Usuario).where(Usuario.email == EMAIL))
        assert check_password_hash(propio.password_hash, NUEVA)
        assert propio.username == "Mati" and propio.email == EMAIL
        assert db.session.scalar(select(Sesion).where(Sesion.usuario_id == otro_id)).activa


def test_intentos_se_limitan_por_cuenta_aunque_cambie_la_ip(app_password, cliente_password):
    app_password.config["AUTH_PASSWORD_ACCOUNT_LIMIT"] = 2
    token = csrf(cliente_password.get("/auth/account"))
    for ip in ["192.0.2.1", "192.0.2.2"]:
        response = cliente_password.post(
            RUTA,
            data=datos(token, actual="incorrecta"),
            environ_overrides={"REMOTE_ADDR": ip},
        )
        assert response.status_code == 400
    limitado = cliente_password.post(
        RUTA, data=datos(token), environ_overrides={"REMOTE_ADDR": "192.0.2.3"}
    )
    assert limitado.status_code == 429
    assert 0 < int(limitado.headers["Retry-After"]) <= 900
    assert "Hubo demasiados intentos" in limitado.get_data(as_text=True)
    with app_password.app_context():
        assert check_password_hash(db.session.scalar(select(Usuario.password_hash)), ACTUAL)
        assert db.session.scalar(select(Sesion)).activa


def test_cambio_de_hash_y_revocacion_se_revierten_juntos_si_falla_guardado(
    app_password, cliente_password, monkeypatch
):
    def fallo_de_guardado():
        raise RuntimeError("Fallo simulado de persistencia")

    with app_password.app_context():
        usuario = db.session.scalar(select(Usuario))
        original = usuario.password_hash
        monkeypatch.setattr(db.session, "commit", fallo_de_guardado)
        with pytest.raises(RuntimeError, match="Fallo simulado"):
            services.cambiar_contrasena(usuario, ACTUAL, NUEVA, NUEVA)
        assert db.session.scalar(select(Usuario.password_hash)) == original
        assert db.session.scalar(select(Sesion)).activa


def test_intentos_se_limitan_por_ip_aunque_cambie_la_cuenta(app_password, cliente_password):
    app_password.config["AUTH_PASSWORD_IP_LIMIT"] = 1
    token = csrf(cliente_password.get("/auth/account"))
    assert cliente_password.post(RUTA, data=datos(token, actual="incorrecta")).status_code == 400
    with app_password.app_context():
        registrar_usuario("Otra persona", "otra@ejemplo.com", ACTUAL)
    otro_cliente = app_password.test_client()
    assert ingresar(otro_cliente, email="otra@ejemplo.com").status_code == 303
    token_ajeno = csrf(otro_cliente.get("/auth/account"))
    limitado = otro_cliente.post(RUTA, data=datos(token_ajeno))
    assert limitado.status_code == 429
    assert int(limitado.headers["Retry-After"]) > 0
    with app_password.app_context():
        assert all(
            check_password_hash(usuario.password_hash, ACTUAL)
            for usuario in db.session.scalars(select(Usuario)).all()
        )


def test_dos_cambios_simultaneos_no_sobrescriben_una_clave_ya_actualizada(
    app_password, monkeypatch
):
    barrera = Barrier(2)
    hash_original = services.generate_password_hash

    def generar_despues_de_comprobar_ambos_actuales(nueva):
        barrera.wait(timeout=10)
        return hash_original(nueva)

    monkeypatch.setattr(
        services, "generate_password_hash", generar_despues_de_comprobar_ambos_actuales
    )

    def intentar(nueva):
        with app_password.app_context():
            usuario = db.session.scalar(select(Usuario))
            try:
                services.cambiar_contrasena(usuario, ACTUAL, nueva, nueva)
            except ValueError:
                return "rechazado"
            return "cambiado"

    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados = list(executor.map(intentar, ["clave-nueva1", "clave-nueva2"]))
    assert sorted(resultados) == ["cambiado", "rechazado"]
    with app_password.app_context():
        guardado = db.session.scalar(select(Usuario.password_hash))
        assert (
            sum(check_password_hash(guardado, valor) for valor in ["clave-nueva1", "clave-nueva2"])
            == 1
        )
