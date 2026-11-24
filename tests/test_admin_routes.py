import pytest

from compilando.extensions import db
from compilando.modules.auth.security import DemasiadosIntentos
from compilando.modules.categories.models import Categoria
from compilando.modules.tags.models import Tag


def test_visitante_no_puede_acceder_a_administracion(app, client):
    respuesta = client.get("/admin/")

    assert respuesta.status_code == 303
    assert "/auth/login" in respuesta.headers["Location"]


def test_usuario_comun_no_puede_acceder_a_administracion(app, cliente_autenticado, usuario):
    cliente = cliente_autenticado(usuario)

    respuesta = cliente.get("/admin/")

    assert respuesta.status_code == 403


def test_administrador_puede_acceder_a_administracion(app, cliente_autenticado, usuario):
    usuario.es_admin = True
    db.session.commit()

    cliente = cliente_autenticado(usuario)

    respuesta = cliente.get("/admin/")

    assert respuesta.status_code == 200


@pytest.mark.parametrize(
    "ruta",
    [
        "/admin/categories",
        "/admin/categories/new",
        "/admin/categories/1/edit",
        "/admin/tags",
        "/admin/tags/new",
        "/admin/tags/1/edit",
    ],
)
def test_usuario_comun_no_puede_acceder_a_rutas_administrativas(
    app, cliente_autenticado, usuario, ruta
):
    cliente = cliente_autenticado(usuario)

    respuesta = cliente.get(ruta)

    assert respuesta.status_code == 403


def test_usuario_comun_no_puede_eliminar_etiquetas(app, cliente_autenticado, usuario):
    cliente = cliente_autenticado(usuario)

    respuesta = cliente.post("/admin/tags/1/delete")

    assert respuesta.status_code == 403


@pytest.mark.parametrize(
    "ruta",
    [
        "/admin/categories",
        "/admin/categories/new",
        "/admin/tags",
        "/admin/tags/new",
    ],
)
def test_administrador_puede_acceder_a_pantallas_de_gestion(
    app, cliente_autenticado, usuario, ruta
):
    usuario.es_admin = True
    db.session.commit()

    cliente = cliente_autenticado(usuario)

    respuesta = cliente.get(ruta)

    assert respuesta.status_code == 200


def test_administrador_puede_acceder_a_edicion_de_categoria(app, cliente_autenticado, usuario):
    usuario.es_admin = True
    db.session.add(
        Categoria(
            nombre="Programación",
            descripcion="Preguntas sobre programación.",
        )
    )
    db.session.commit()

    cliente = cliente_autenticado(usuario)

    respuesta = cliente.get("/admin/categories/1/edit")

    assert respuesta.status_code == 200


def test_administrador_puede_acceder_a_edicion_de_etiqueta(app, cliente_autenticado, usuario):
    usuario.es_admin = True
    db.session.add(Tag(nombre="Python"))
    db.session.commit()

    cliente = cliente_autenticado(usuario)

    respuesta = cliente.get("/admin/tags/1/edit")

    assert respuesta.status_code == 200


def test_administrador_puede_crear_categoria(app, cliente_autenticado, usuario):
    usuario.es_admin = True
    db.session.commit()
    cliente = cliente_autenticado(usuario)

    respuesta = cliente.post(
        "/admin/categories/new",
        data={
            "nombre": "Programación",
            "descripcion": "Preguntas sobre programación.",
        },
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["Location"].endswith("/admin/categories")

    categoria = db.session.query(Categoria).filter_by(nombre="Programación").first()

    assert categoria is not None
    assert categoria.descripcion == "Preguntas sobre programación."


def test_administrador_puede_crear_etiqueta(app, cliente_autenticado, usuario):
    usuario.es_admin = True
    db.session.commit()
    cliente = cliente_autenticado(usuario)

    respuesta = cliente.post(
        "/admin/tags/new",
        data={"nombre": "Python"},
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["Location"].endswith("/admin/tags")

    etiqueta = db.session.query(Tag).filter_by(nombre="Python").first()

    assert etiqueta is not None


def test_crear_categoria_con_datos_invalidos_no_guarda(app, cliente_autenticado, usuario):
    usuario.es_admin = True
    db.session.commit()
    cliente = cliente_autenticado(usuario)

    respuesta = cliente.post(
        "/admin/categories/new",
        data={
            "nombre": "   ",
            "descripcion": "Descripción válida.",
        },
    )

    assert respuesta.status_code == 200
    assert db.session.query(Categoria).count() == 0


def test_crear_etiqueta_con_nombre_vacio_no_guarda(app, cliente_autenticado, usuario):
    usuario.es_admin = True
    db.session.commit()
    cliente = cliente_autenticado(usuario)

    respuesta = cliente.post(
        "/admin/tags/new",
        data={"nombre": "   "},
    )

    assert respuesta.status_code == 200
    assert db.session.query(Tag).count() == 0


def test_administrador_puede_editar_categoria(app, cliente_autenticado, usuario):
    usuario.es_admin = True
    categoria = Categoria(
        nombre="Programación",
        descripcion="Preguntas sobre programación.",
    )
    db.session.add(categoria)
    db.session.commit()

    cliente = cliente_autenticado(usuario)

    respuesta = cliente.post(
        f"/admin/categories/{categoria.id}/edit",
        data={
            "nombre": "Algoritmos",
            "descripcion": "Preguntas sobre algoritmos.",
        },
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["Location"].endswith("/admin/categories")

    db.session.refresh(categoria)
    assert categoria.nombre == "Algoritmos"
    assert categoria.descripcion == "Preguntas sobre algoritmos."


def test_administrador_puede_editar_etiqueta(app, cliente_autenticado, usuario):
    usuario.es_admin = True
    etiqueta = Tag(nombre="Python")
    db.session.add(etiqueta)
    db.session.commit()

    cliente = cliente_autenticado(usuario)

    respuesta = cliente.post(
        f"/admin/tags/{etiqueta.id}/edit",
        data={"nombre": "Java"},
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["Location"].endswith("/admin/tags")

    db.session.refresh(etiqueta)
    assert etiqueta.nombre == "Java"


def test_administrador_puede_eliminar_etiqueta(app, cliente_autenticado, usuario):
    usuario.es_admin = True
    etiqueta = Tag(nombre="Python")
    db.session.add(etiqueta)
    db.session.commit()

    cliente = cliente_autenticado(usuario)

    respuesta = cliente.post(f"/admin/tags/{etiqueta.id}/delete")

    assert respuesta.status_code == 303
    assert respuesta.headers["Location"].endswith("/admin/tags")
    assert db.session.get(Tag, etiqueta.id) is None


def test_eliminar_etiqueta_inexistente_redirige(app, cliente_autenticado, usuario):
    usuario.es_admin = True
    db.session.commit()
    cliente = cliente_autenticado(usuario)

    respuesta = cliente.post("/admin/tags/999/delete")

    assert respuesta.status_code == 303
    assert respuesta.headers["Location"].endswith("/admin/tags")


def test_usuario_puede_activar_su_cuenta_como_administrador(app, cliente_autenticado, usuario):
    app.config["ADMIN_ACTIVATION_CODE"] = "codigo-de-prueba"
    cliente = cliente_autenticado(usuario)

    respuesta = cliente.post(
        "/admin/activate",
        data={"codigo_activacion": "codigo-de-prueba"},
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["Location"].endswith("/auth/account")

    db.session.refresh(usuario)
    assert usuario.es_admin is True


def test_usuario_no_puede_activar_con_codigo_incorrecto(app, cliente_autenticado, usuario):
    app.config["ADMIN_ACTIVATION_CODE"] = "codigo-de-prueba"
    cliente = cliente_autenticado(usuario)

    respuesta = cliente.post(
        "/admin/activate",
        data={"codigo_activacion": "codigo-incorrecto"},
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["Location"].endswith("/auth/account")

    db.session.refresh(usuario)
    assert usuario.es_admin is False


def test_activacion_no_disponible_si_no_hay_codigo_configurado(app, cliente_autenticado, usuario):
    app.config["ADMIN_ACTIVATION_CODE"] = ""
    cliente = cliente_autenticado(usuario)

    respuesta = cliente.post(
        "/admin/activate",
        data={"codigo_activacion": "cualquier-codigo"},
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["Location"].endswith("/auth/account")

    db.session.refresh(usuario)
    assert usuario.es_admin is False


def test_administrador_no_necesita_activarse_nuevamente(app, cliente_autenticado, usuario):
    usuario.es_admin = True
    db.session.commit()
    cliente = cliente_autenticado(usuario)

    respuesta = cliente.post(
        "/admin/activate",
        data={"codigo_activacion": "cualquier-codigo"},
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["Location"].endswith("/auth/account")

    db.session.refresh(usuario)
    assert usuario.es_admin is True


def test_activacion_bloqueada_por_demasiados_intentos(
    app, cliente_autenticado, usuario, monkeypatch
):
    cliente = cliente_autenticado(usuario)

    def simular_bloqueo(*args, **kwargs):
        raise DemasiadosIntentos(120)

    monkeypatch.setattr(
        "compilando.modules.admin.routes.limitar_intentos",
        simular_bloqueo,
    )

    respuesta = cliente.post(
        "/admin/activate",
        data={"codigo_activacion": "codigo-de-prueba"},
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["Location"].endswith("/auth/account")
    assert respuesta.headers["Retry-After"] == "120"

    db.session.refresh(usuario)
    assert usuario.es_admin is False


def test_buscar_categoria_desde_panel_administrativo(app, cliente_autenticado, usuario):
    usuario.es_admin = True
    db.session.add_all(
        [
            Categoria(nombre="Programación", descripcion="Preguntas de programación."),
            Categoria(nombre="Matemática", descripcion="Preguntas de matemática."),
        ]
    )
    db.session.commit()

    cliente = cliente_autenticado(usuario)

    respuesta = cliente.get("/admin/categories?busqueda_categoria=program")

    assert respuesta.status_code == 200
    assert b"Programaci" in respuesta.data
    assert b"Matem" not in respuesta.data


def test_buscar_etiqueta_desde_panel_administrativo(app, cliente_autenticado, usuario):
    usuario.es_admin = True
    db.session.add_all(
        [
            Tag(nombre="Python"),
            Tag(nombre="Java"),
        ]
    )
    db.session.commit()

    cliente = cliente_autenticado(usuario)

    respuesta = cliente.get("/admin/tags?busqueda_etiqueta=pyth")

    assert respuesta.status_code == 200
    assert b"Python" in respuesta.data
    assert b"Java" not in respuesta.data


def test_paginacion_de_categorias(app, cliente_autenticado, usuario):
    usuario.es_admin = True

    db.session.add_all(
        [
            Categoria(
                nombre=f"Categoría {i:02}",
                descripcion=f"Descripción de categoría {i}.",
            )
            for i in range(1, 13)
        ]
    )
    db.session.commit()

    cliente = cliente_autenticado(usuario)

    primera = cliente.get("/admin/categories")
    segunda = cliente.get("/admin/categories?pagina=2")

    assert primera.status_code == 200
    assert segunda.status_code == 200

    assert b"Categor\xc3\xada 01" in primera.data
    assert b"Categor\xc3\xada 11" not in primera.data

    assert b"Categor\xc3\xada 11" in segunda.data
    assert b"Categor\xc3\xada 01" not in segunda.data


def test_paginacion_de_etiquetas(app, cliente_autenticado, usuario):
    usuario.es_admin = True

    db.session.add_all([Tag(nombre=f"Etiqueta{i:02}") for i in range(1, 13)])
    db.session.commit()

    cliente = cliente_autenticado(usuario)

    primera = cliente.get("/admin/tags")
    segunda = cliente.get("/admin/tags?pagina=2")

    assert primera.status_code == 200
    assert segunda.status_code == 200

    assert b"Etiqueta01" in primera.data
    assert b"Etiqueta11" not in primera.data

    assert b"Etiqueta11" in segunda.data
    assert b"Etiqueta01" not in segunda.data


def test_pagina_inferior_a_un_se_ajusta_a_primera_pagina(app, cliente_autenticado, usuario):
    usuario.es_admin = True
    db.session.add(
        Categoria(
            nombre="Programación",
            descripcion="Preguntas sobre programación.",
        )
    )
    db.session.commit()

    cliente = cliente_autenticado(usuario)

    respuesta = cliente.get("/admin/categories?pagina=0")

    assert respuesta.status_code == 200
    assert b"Programaci" in respuesta.data


def test_pagina_superior_a_ultima_se_ajusta(app, cliente_autenticado, usuario):
    usuario.es_admin = True
    db.session.add(Tag(nombre="Python"))
    db.session.commit()

    cliente = cliente_autenticado(usuario)

    respuesta = cliente.get("/admin/tags?pagina=999")

    assert respuesta.status_code == 200
    assert b"Python" in respuesta.data


def test_editar_categoria_inexistente_redirige(app, cliente_autenticado, usuario):
    usuario.es_admin = True
    db.session.commit()
    cliente = cliente_autenticado(usuario)

    respuesta = cliente.get("/admin/categories/999/edit")

    assert respuesta.status_code == 303
    assert respuesta.headers["Location"].endswith("/admin/categories")


def test_editar_etiqueta_inexistente_redirige(app, cliente_autenticado, usuario):
    usuario.es_admin = True
    db.session.commit()
    cliente = cliente_autenticado(usuario)

    respuesta = cliente.get("/admin/tags/999/edit")

    assert respuesta.status_code == 303
    assert respuesta.headers["Location"].endswith("/admin/tags")
