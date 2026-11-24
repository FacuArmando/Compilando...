import pytest

from compilando.extensions import db
from compilando.modules.admin.services import (
    activar_administrador,
    crear_categoria,
    crear_tag,
    editar_categoria,
    editar_tag,
    eliminar_tag,
)
from compilando.modules.categories.models import Categoria
from compilando.modules.questions.models import Pregunta
from compilando.modules.questions.services import publicar_pregunta
from compilando.modules.tags.models import Tag


@pytest.fixture
def categoria():
    categoria = Categoria(
        nombre="Programación",
        descripcion="Preguntas sobre programación.",
    )
    db.session.add(categoria)
    db.session.commit()
    return categoria


@pytest.fixture
def tag():
    tag = Tag(nombre="Python")
    db.session.add(tag)
    db.session.commit()
    return tag


def test_activar_administrador_con_codigo_correcto(app, usuario):
    app.config["ADMIN_ACTIVATION_CODE"] = "codigo-de-prueba"

    resultado = activar_administrador(usuario, "codigo-de-prueba")

    assert resultado is True
    assert usuario.es_admin is True

    db.session.refresh(usuario)
    assert usuario.es_admin is True


def test_activar_administrador_con_codigo_incorrecto(app, usuario):
    app.config["ADMIN_ACTIVATION_CODE"] = "codigo-de-prueba"

    with pytest.raises(ValueError, match="incorrecto"):
        activar_administrador(usuario, "codigo-incorrecto")

    assert usuario.es_admin is False


def test_activar_administrador_con_codigo_vacio(app, usuario):
    app.config["ADMIN_ACTIVATION_CODE"] = "codigo-de-prueba"

    with pytest.raises(ValueError, match="Ingresá un código"):
        activar_administrador(usuario, "")

    assert usuario.es_admin is False


def test_activar_administrador_sin_codigo_configurado(app, usuario):
    app.config["ADMIN_ACTIVATION_CODE"] = ""

    with pytest.raises(RuntimeError, match="no está configurado"):
        activar_administrador(usuario, "cualquier-codigo")

    assert usuario.es_admin is False


def test_activar_administrador_si_ya_es_admin(app, usuario):
    usuario.es_admin = True
    db.session.commit()

    app.config["ADMIN_ACTIVATION_CODE"] = "codigo-de-prueba"

    resultado = activar_administrador(usuario, "codigo-de-prueba")

    assert resultado is False
    assert usuario.es_admin is True


def test_crear_categoria_correctamente(app):
    categoria = crear_categoria(
        "  Estructuras de datos  ",
        "  Preguntas sobre estructuras.  ",
    )

    assert categoria.id is not None
    assert categoria.nombre == "Estructuras de datos"
    assert categoria.descripcion == "Preguntas sobre estructuras."


def test_crear_categoria_con_nombre_vacio(app):
    with pytest.raises(ValueError, match="nombre"):
        crear_categoria("   ", "Descripción válida.")


def test_crear_categoria_con_descripcion_vacia(app):
    with pytest.raises(ValueError, match="descripción"):
        crear_categoria("Programación", "   ")


def test_crear_categoria_con_nombre_demasiado_largo(app):
    with pytest.raises(ValueError, match="100 caracteres"):
        crear_categoria("A" * 101, "Descripción válida.")


def test_crear_categoria_con_nombre_duplicado(app, categoria):
    with pytest.raises(ValueError, match="Ya existe"):
        crear_categoria("PROGRAMACION", "Otra descripción.")


def test_crear_categoria_con_nombre_duplicado_sin_acento(app, categoria):
    with pytest.raises(ValueError, match="Ya existe"):
        crear_categoria("Programacion", "Otra descripción.")


def test_editar_categoria_correctamente(app, categoria):
    resultado = editar_categoria(
        categoria.id,
        "Algoritmos",
        "Preguntas sobre algoritmos.",
    )

    assert resultado.nombre == "Algoritmos"
    assert resultado.descripcion == "Preguntas sobre algoritmos."


def test_editar_categoria_conservando_su_nombre(app, categoria):
    resultado = editar_categoria(
        categoria.id,
        "PROGRAMACIÓN",
        "Nueva descripción.",
    )

    assert resultado.nombre == "PROGRAMACIÓN"
    assert resultado.descripcion == "Nueva descripción."


def test_editar_categoria_con_nombre_vacio(app, categoria):
    with pytest.raises(ValueError, match="nombre"):
        editar_categoria(categoria.id, "   ", "Descripción válida.")


def test_editar_categoria_con_descripcion_vacia(app, categoria):
    with pytest.raises(ValueError, match="descripción"):
        editar_categoria(categoria.id, "Programación", "   ")


def test_editar_categoria_con_nombre_duplicado(app, categoria):
    crear_categoria("Bases de datos", "Consultas sobre bases de datos.")

    with pytest.raises(ValueError, match="Ya existe"):
        editar_categoria(
            categoria.id,
            "BASES DE DATOS",
            "Otra descripción.",
        )


def test_editar_categoria_inexistente(app):
    with pytest.raises(LookupError, match="no existe"):
        editar_categoria(999, "Algoritmos", "Descripción válida.")


def test_crear_tag_correctamente(app):
    tag = crear_tag("  Python  ")

    assert tag.id is not None
    assert tag.nombre == "Python"


def test_crear_tag_con_nombre_vacio(app):
    with pytest.raises(ValueError, match="nombre"):
        crear_tag("   ")


def test_crear_tag_con_nombre_demasiado_largo(app):
    with pytest.raises(ValueError, match="50 caracteres"):
        crear_tag("A" * 51)


def test_crear_tag_con_nombre_duplicado(app, tag):
    with pytest.raises(ValueError, match="Ya existe"):
        crear_tag("PYTHON")


def test_crear_tag_con_nombre_duplicado_sin_acento(app):
    crear_tag("Programación")

    with pytest.raises(ValueError, match="Ya existe"):
        crear_tag("Programacion")


def test_editar_tag_correctamente(app, tag):
    resultado = editar_tag(tag.id, "Java")

    assert resultado.nombre == "Java"


def test_editar_tag_conservando_su_nombre(app, tag):
    resultado = editar_tag(tag.id, "PYTHON")

    assert resultado.nombre == "PYTHON"


def test_editar_tag_con_nombre_vacio(app, tag):
    with pytest.raises(ValueError, match="nombre"):
        editar_tag(tag.id, "   ")


def test_editar_tag_con_nombre_demasiado_largo(app, tag):
    with pytest.raises(ValueError, match="50 caracteres"):
        editar_tag(tag.id, "A" * 51)


def test_editar_tag_con_nombre_duplicado(app, tag):
    crear_tag("Java")

    with pytest.raises(ValueError, match="Ya existe"):
        editar_tag(tag.id, "JAVA")


def test_editar_tag_inexistente(app):
    with pytest.raises(LookupError, match="no existe"):
        editar_tag(999, "Java")


def test_eliminar_tag_conserva_las_preguntas_y_sus_otras_etiquetas(app, usuario, tag):
    pregunta = publicar_pregunta(
        "¿Cómo funciona Python?",
        "Quiero conocer sus fundamentos.",
        "Programación",
        ["Python", "Java"],
        usuario,
    )

    resultado = eliminar_tag(tag.id)

    assert resultado is None
    assert db.session.get(Tag, tag.id) is None
    assert db.session.get(Pregunta, pregunta.id) is not None
    assert [etiqueta.nombre for etiqueta in pregunta.tags] == ["Java"]


def test_eliminar_tag_inexistente(app):
    with pytest.raises(LookupError, match="no existe"):
        eliminar_tag(999)
