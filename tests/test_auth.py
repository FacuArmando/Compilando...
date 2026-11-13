"""Comprueba las migraciones y el registro de usuarios en bases temporales."""

from html.parser import HTMLParser

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect, select
from werkzeug.security import check_password_hash, generate_password_hash

from compilando import create_app
from compilando.extensions import db
from compilando.modules.auth import Usuario
from compilando.modules.auth.services import registrar_usuario


@pytest.fixture
def app_con_usuarios(tmp_path):
    database_path = tmp_path / "registro.sqlite"
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "clave-solo-para-pruebas",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path.as_posix()}",
        }
    )
    with app.app_context():
        upgrade()
        yield app
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def cliente_registro(app_con_usuarios):
    return app_con_usuarios.test_client()


class CamposFormulario(HTMLParser):
    """Lee los campos del HTML para probar el formulario como lo recibe el navegador."""

    def __init__(self):
        super().__init__()
        self.campos = {}

    def handle_starttag(self, tag, attrs):
        atributos = dict(attrs)
        if tag == "input":
            self.campos[atributos["name"]] = atributos


def campos_formulario(response):
    parser = CamposFormulario()
    parser.feed(response.get_data(as_text=True))
    return parser.campos


def test_migracion_usuarios_crea_y_revierte_tabla(tmp_path):
    database_path = tmp_path / "usuarios.sqlite"
    app = create_app(
        {"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path.as_posix()}"}
    )

    with app.app_context():
        upgrade()
        assert "usuarios" in inspect(db.engine).get_table_names()

        usuario = Usuario(
            username="usuario_prueba",
            email="prueba@example.com",
            password_hash=generate_password_hash("clave-de-prueba"),
        )
        db.session.add(usuario)
        db.session.commit()
        usuario_id = usuario.id
        db.session.remove()

        guardado = db.session.get(Usuario, usuario_id)
        assert guardado is not None
        assert guardado.username == "usuario_prueba"
        assert guardado.email == "prueba@example.com"
        assert check_password_hash(guardado.password_hash, "clave-de-prueba")
        db.session.remove()

        # La reversión se prueba únicamente en esta base temporal.
        downgrade(revision="base")
        assert "usuarios" not in inspect(db.engine).get_table_names()

        upgrade()
        assert db.session.scalars(select(Usuario)).all() == []
        db.session.remove()
        db.engine.dispose()


def test_registro_guarda_usuario_y_hash_sin_modificar_la_contrasena(app_con_usuarios):
    password = " clave-de-prueba "
    usuario = registrar_usuario("  Mati  ", "  MATI@EJEMPLO.COM  ", password)
    usuario_id = usuario.id
    db.session.remove()

    guardado = db.session.get(Usuario, usuario_id)
    assert guardado is not None
    assert guardado.username == "Mati"
    assert guardado.email == "mati@ejemplo.com"
    assert guardado.password_hash != password
    assert check_password_hash(guardado.password_hash, password)
    assert not check_password_hash(guardado.password_hash, password.strip())


@pytest.mark.parametrize(
    ("campo", "valor", "mensaje"),
    [
        ("username", "", "Completá"),
        ("username", "   ", "Completá"),
        ("email", "", "Completá"),
        ("email", "   ", "Completá"),
        ("password", "", "Completá"),
        ("password", "        ", "Completá"),
        ("username", "u" * 81, "como máximo 80"),
        ("email", "sin-arroba", "correo electrónico válido"),
        ("email", "@ejemplo.com", "correo electrónico válido"),
        ("email", "mati@", "correo electrónico válido"),
        ("email", "mati@ejemplo", "correo electrónico válido"),
        ("email", "ma ti@ejemplo.com", "correo electrónico válido"),
        ("email", "mati@@ejemplo.com", "correo electrónico válido"),
        ("email", "m" * 243 + "@ejemplo.com", "correo electrónico válido"),
        ("password", "p" * 7, "entre 8 y 128"),
        ("password", "p" * 129, "entre 8 y 128"),
    ],
)
def test_registro_rechaza_datos_invalidos(app_con_usuarios, campo, valor, mensaje):
    datos = {"username": "mati", "email": "mati@ejemplo.com", "password": "clave-de-prueba"}
    datos[campo] = valor

    with pytest.raises(ValueError, match=mensaje):
        registrar_usuario(**datos)

    assert db.session.scalars(select(Usuario)).all() == []


@pytest.mark.parametrize("password", ["p" * 8, "p" * 128])
def test_registro_acepta_los_limites_de_longitud_de_contrasena(app_con_usuarios, password):
    usuario = registrar_usuario("mati", "mati@ejemplo.com", password)
    assert check_password_hash(usuario.password_hash, password)


@pytest.mark.parametrize(
    ("username", "email", "mensaje"),
    [
        ("  mati  ", "otro@ejemplo.com", "nombre de usuario ya está registrado"),
        ("otro", " MATI@EJEMPLO.COM ", "correo electrónico ya está registrado"),
    ],
)
def test_registro_rechaza_duplicados_y_permite_reintentar(
    app_con_usuarios, username, email, mensaje
):
    registrar_usuario("mati", "mati@ejemplo.com", "clave-de-prueba")

    with pytest.raises(ValueError, match=mensaje):
        registrar_usuario(username, email, "otra-clave-de-prueba")

    assert len(db.session.scalars(select(Usuario)).all()) == 1

    nuevo = registrar_usuario("nuevo", "nuevo@ejemplo.com", "otra-clave-de-prueba")
    assert nuevo.id is not None
    assert len(db.session.scalars(select(Usuario)).all()) == 2


def test_formulario_registra_y_confirma_sin_reenviar_al_recargar(cliente_registro):
    formulario = cliente_registro.get("/auth/register")
    assert formulario.status_code == 200
    token = campos_formulario(formulario)["csrf_token"]["value"]

    response = cliente_registro.post(
        "/auth/register",
        data={
            "csrf_token": token,
            "username": "  Mati  ",
            "email": " MATI@EJEMPLO.COM ",
            "password": "clave-de-prueba",
        },
    )
    assert response.status_code == 303
    assert response.headers["Location"] == "/"
    db.session.remove()

    usuario = db.session.scalar(select(Usuario).where(Usuario.email == "mati@ejemplo.com"))
    assert usuario is not None
    assert usuario.username == "Mati"
    assert check_password_hash(usuario.password_hash, "clave-de-prueba")

    inicio = cliente_registro.get(response.headers["Location"])
    assert "Tu cuenta se creó correctamente." in inicio.get_data(as_text=True)
    recarga = cliente_registro.get("/")
    assert "Tu cuenta se creó correctamente." not in recarga.get_data(as_text=True)
    assert len(db.session.scalars(select(Usuario)).all()) == 1


@pytest.mark.parametrize("token", [None, "token-invalido"])
def test_formulario_rechaza_csrf_invalido_y_permite_reintentar(cliente_registro, token):
    datos = {"username": "mati", "email": "mati@ejemplo.com", "password": "clave-de-prueba"}
    if token is not None:
        datos["csrf_token"] = token

    response = cliente_registro.post("/auth/register", data=datos)
    assert response.status_code == 400
    assert "El formulario venció o no es válido." in response.get_data(as_text=True)
    assert db.session.scalars(select(Usuario)).all() == []

    campos = campos_formulario(response)
    assert campos["username"]["value"] == "mati"
    assert campos["email"]["value"] == "mati@ejemplo.com"
    assert "value" not in campos["password"]
    assert "clave-de-prueba" not in response.get_data(as_text=True)

    datos["csrf_token"] = campos["csrf_token"]["value"]
    reintento = cliente_registro.post("/auth/register", data=datos)
    assert reintento.status_code == 303
    assert len(db.session.scalars(select(Usuario)).all()) == 1


def test_formulario_rechaza_token_de_otro_navegador(cliente_registro, app_con_usuarios):
    otro_cliente = app_con_usuarios.test_client()
    # Cada navegador genera su token en un contexto independiente.
    with app_con_usuarios.app_context():
        token_ajeno = campos_formulario(otro_cliente.get("/auth/register"))["csrf_token"]["value"]
    token_propio = campos_formulario(cliente_registro.get("/auth/register"))["csrf_token"]["value"]
    assert token_ajeno != token_propio

    response = cliente_registro.post(
        "/auth/register",
        data={
            "csrf_token": token_ajeno,
            "username": "mati",
            "email": "mati@ejemplo.com",
            "password": "clave-de-prueba",
        },
    )
    assert response.status_code == 400
    assert db.session.scalars(select(Usuario)).all() == []

    reintento = cliente_registro.post(
        "/auth/register",
        data={
            "csrf_token": token_propio,
            "username": "mati",
            "email": "mati@ejemplo.com",
            "password": "clave-de-prueba",
        },
    )
    assert reintento.status_code == 303


def test_formulario_rechaza_token_vencido(cliente_registro, app_con_usuarios):
    # Forzar el vencimiento sin demorar la prueba.
    app_con_usuarios.config["WTF_CSRF_TIME_LIMIT"] = -1
    token = campos_formulario(cliente_registro.get("/auth/register"))["csrf_token"]["value"]

    response = cliente_registro.post(
        "/auth/register",
        data={
            "csrf_token": token,
            "username": "mati",
            "email": "mati@ejemplo.com",
            "password": "clave-de-prueba",
        },
    )
    assert response.status_code == 400
    assert "El formulario venció o no es válido." in response.get_data(as_text=True)
    assert db.session.scalars(select(Usuario)).all() == []


@pytest.mark.parametrize(
    ("campo", "valor", "mensaje"),
    [
        ("username", "", "Completá"),
        ("email", "correo-invalido", "correo electrónico válido"),
        ("password", "corta", "entre 8 y 128"),
    ],
)
def test_formulario_muestra_errores_sin_guardar_ni_repetir_contrasena(
    cliente_registro, campo, valor, mensaje
):
    datos = {
        "csrf_token": campos_formulario(cliente_registro.get("/auth/register"))["csrf_token"][
            "value"
        ],
        "username": "mati",
        "email": "mati@ejemplo.com",
        "password": "clave-de-prueba",
    }
    datos[campo] = valor

    response = cliente_registro.post("/auth/register", data=datos)
    assert response.status_code == 400
    assert mensaje in response.get_data(as_text=True)
    campos = campos_formulario(response)
    assert campos["username"]["value"] == datos["username"]
    assert campos["email"]["value"] == datos["email"]
    assert "value" not in campos["password"]
    assert datos["password"] not in response.get_data(as_text=True)
    assert db.session.scalars(select(Usuario)).all() == []


@pytest.mark.parametrize(
    ("username", "email", "mensaje"),
    [
        ("mati", "otro@ejemplo.com", "nombre de usuario ya está registrado"),
        ("otro", "MATI@EJEMPLO.COM", "correo electrónico ya está registrado"),
    ],
)
def test_formulario_informa_duplicados(cliente_registro, username, email, mensaje):
    registrar_usuario("mati", "mati@ejemplo.com", "clave-de-prueba")
    token = campos_formulario(cliente_registro.get("/auth/register"))["csrf_token"]["value"]

    response = cliente_registro.post(
        "/auth/register",
        data={
            "csrf_token": token,
            "username": username,
            "email": email,
            "password": "otra-clave-de-prueba",
        },
    )
    assert response.status_code == 400
    assert mensaje in response.get_data(as_text=True)
    assert len(db.session.scalars(select(Usuario)).all()) == 1


def test_formulario_escapa_datos_al_mostrar_error(cliente_registro):
    token = campos_formulario(cliente_registro.get("/auth/register"))["csrf_token"]["value"]
    username = '"><script>alert(1)</script>'
    response = cliente_registro.post(
        "/auth/register",
        data={
            "csrf_token": token,
            "username": username,
            "email": "correo-invalido",
            "password": "clave-de-prueba",
        },
    )
    assert response.status_code == 400
    assert "<script>" not in response.get_data(as_text=True)
    assert campos_formulario(response)["username"]["value"] == username
    assert db.session.scalars(select(Usuario)).all() == []
