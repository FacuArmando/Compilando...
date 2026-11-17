from datetime import datetime

import pytest

from compilando.extensions import db
from compilando.modules.answers.models import Respuesta
from compilando.modules.answers.services import (
    editar_respuesta,
    publicar_respuesta,
    validar_cuerpo,
)
from compilando.modules.auth.models import Usuario
from compilando.modules.questions.services import publicar_pregunta


@pytest.mark.parametrize(
    "cuerpo",
    [
        "Sí.",  # 3 caracteres
        "A" * 5000,  # 5000 caracteres
        "   Respuesta válida con espacios   ",
    ],
)
def test_validar_cuerpo_respuesta_valido(cuerpo):
    assert validar_cuerpo(cuerpo) is True


@pytest.mark.parametrize(
    "cuerpo",
    [
        "No",  # Menos de 3 caracteres
        "A" * 5001,  # Más de 5000 caracteres
        "     ",  # Solo espacios
        "",
    ],
)
def test_validar_cuerpo_respuesta_invalido(cuerpo):
    assert validar_cuerpo(cuerpo) is False


def test_publicar_respuesta_exitosa(app, usuario):
    pregunta = publicar_pregunta(
        titulo="¿Cómo funciona SQLAlchemy?",
        cuerpo="Necesito entender cómo se relacionan las tablas en Flask.",
        categoria_nombre="Python",
        nombres_tags=["flask", "sqlalchemy"],
        usuario=usuario,
    )

    respuesta = publicar_respuesta(
        pregunta_id=pregunta.id,
        cuerpo="Usando relationship y ForeignKey entre los modelos.",
        usuario=usuario,
    )

    assert respuesta.id is not None
    assert respuesta.cuerpo == "Usando relationship y ForeignKey entre los modelos."
    assert respuesta.pregunta_id == pregunta.id
    assert respuesta.usuario_id == usuario.id
    assert len(pregunta.respuestas) == 1


def test_publicar_respuesta_pregunta_inexistente(app, usuario):
    with pytest.raises(ValueError, match="no existe"):
        publicar_respuesta(
            pregunta_id=9999,
            cuerpo="Esta respuesta no debería guardarse.",
            usuario=usuario,
        )


def test_publicar_respuesta_cuerpo_invalido(app, usuario):
    pregunta = publicar_pregunta(
        titulo="¿Cómo funciona pytest?",
        cuerpo="Quiero escribir pruebas unitarias en mi proyecto.",
        categoria_nombre="Testing",
        nombres_tags=["pytest"],
        usuario=usuario,
    )

    with pytest.raises(ValueError, match="entre 3 y 5000 caracteres"):
        publicar_respuesta(
            pregunta_id=pregunta.id,
            cuerpo="ab",
            usuario=usuario,
        )


def test_formato_fecha_respuesta():
    respuesta = Respuesta(
        cuerpo="Prueba de fecha",
        fecha=datetime(2026, 11, 16, 20, 58),
    )
    assert respuesta.fecha_formateada == "lunes 16 de noviembre de 2026, a las 20:58 pm"


def test_ruta_publicar_respuesta_requiere_login(app, usuario):
    pregunta = publicar_pregunta(
        titulo="¿Cómo proteger rutas en Flask?",
        cuerpo="Quiero evitar que usuarios anónimos publiquen respuestas.",
        categoria_nombre="Seguridad",
        nombres_tags=["flask"],
        usuario=usuario,
    )

    cliente = app.test_client()
    response = cliente.post(
        f"/questions/{pregunta.id}/answers",
        data={"cuerpo": "Intento sin sesión"},
    )
    assert response.status_code == 401


def test_editar_respuesta_exitosa(app, usuario):
    pregunta = publicar_pregunta(
        titulo="¿Cómo editar en SQLAlchemy?",
        cuerpo="Quiero probar la actualización de registros en la base.",
        categoria_nombre="Python",
        nombres_tags=["sqlalchemy"],
        usuario=usuario,
    )
    respuesta = publicar_respuesta(
        pregunta_id=pregunta.id,
        cuerpo="Texto original de la respuesta.",
        usuario=usuario,
    )

    editada = editar_respuesta(
        respuesta_id=respuesta.id,
        nuevo_cuerpo="Texto actualizado correctamente.",
        usuario=usuario,
    )

    assert editada.cuerpo == "Texto actualizado correctamente."
    assert editada.fecha_edicion is not None
    assert editada.fecha_edicion_formateada is not None


def test_editar_respuesta_otro_usuario_falla(app, usuario):
    otro_usuario = Usuario(
        username="intruso", email="intruso@test.com", password_hash="hash_otro"
    )
    db.session.add(otro_usuario)
    db.session.commit()

    pregunta = publicar_pregunta(
        titulo="¿Cómo validar permisos en Flask?",
        cuerpo="Necesito evitar que un usuario modifique contenido ajeno.",
        categoria_nombre="Seguridad",
        nombres_tags=["permisos"],
        usuario=usuario,
    )
    respuesta = publicar_respuesta(
        pregunta_id=pregunta.id,
        cuerpo="Respuesta privada del autor original.",
        usuario=usuario,
    )

    with pytest.raises(PermissionError, match="Solo el autor"):
        editar_respuesta(
            respuesta_id=respuesta.id,
            nuevo_cuerpo="Intento de modificación no autorizada.",
            usuario=otro_usuario,
        )


def test_editar_respuesta_cuerpo_invalido(app, usuario):
    pregunta = publicar_pregunta(
        titulo="¿Cómo validar longitud al editar?",
        cuerpo="Probando límites de caracteres en edición.",
        categoria_nombre="Validaciones",
        nombres_tags=["forms"],
        usuario=usuario,
    )
    respuesta = publicar_respuesta(
        pregunta_id=pregunta.id,
        cuerpo="Respuesta válida inicial.",
        usuario=usuario,
    )

    with pytest.raises(ValueError, match="entre 3 y 5000 caracteres"):
        editar_respuesta(
            respuesta_id=respuesta.id,
            nuevo_cuerpo="no",
            usuario=usuario,
        )
