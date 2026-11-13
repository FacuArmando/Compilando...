"""Recorridos reales de autenticación y rechazo de intentos de evadir sus controles."""

import hashlib
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from html.parser import HTMLParser

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import delete, inspect, select, update

from compilando import create_app
from compilando.extensions import db
from compilando.modules.auth.models import LimiteIntentos, Sesion, Usuario
from compilando.modules.auth.services import (
    ERROR_CREDENCIALES,
    autenticar_usuario,
    registrar_usuario,
)
from compilando.modules.auth.sessions import ahora_utc

PASSWORD = "clave-de-prueba"
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
    assert "Sesión iniciada como <strong>Mati</strong>" in inicio.get_data(as_text=True)
    assert "Cerrar sesión" in inicio.get_data(as_text=True)
    assert PASSWORD not in inicio.get_data(as_text=True)
    assert cliente.get("/auth/login").status_code == 302
    assert "HttpOnly" in response.headers["Set-Cookie"]
    assert "SameSite=Lax" in response.headers["Set-Cookie"]


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


def test_contrasena_con_espacios_se_comprueba_sin_recortarla(app_login):
    with app_login.app_context():
        registrar_usuario("otro", "otro@ejemplo.com", " clave-de-prueba ")
        assert autenticar_usuario("otro@ejemplo.com", " clave-de-prueba ").username == "otro"
        with pytest.raises(ValueError, match=ERROR_CREDENCIALES):
            autenticar_usuario("otro@ejemplo.com", "clave-de-prueba")


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
        assert db.session.scalar(select(Usuario)).email == EMAIL
        db.session.remove()
        upgrade()
        assert "sesiones" in inspect(db.engine).get_table_names()
        assert db.session.scalar(select(Usuario)).email == EMAIL
