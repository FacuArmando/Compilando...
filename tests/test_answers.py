from datetime import datetime

import pytest

from compilando.extensions import db
from compilando.modules.answers.models import EstadoRespuesta, Respuesta
from compilando.modules.answers.services import (
    aceptar_respuesta,
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


def test_ruta_publicar_respuesta_requiere_login(app, usuario, client):
    pregunta = publicar_pregunta(
        titulo="¿Cómo proteger rutas en Flask?",
        cuerpo="Quiero evitar que usuarios anónimos publiquen respuestas.",
        categoria_nombre="Seguridad",
        nombres_tags=["flask"],
        usuario=usuario,
    )

    response = client.post(
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
    otro_usuario = Usuario(username="intruso", email="intruso@test.com", password_hash="hash_otro")
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


def test_identificacion_autor_humano_y_autor_pregunta(app, usuario):
    otro_usuario = Usuario(
        username="colaborador", email="colab@test.com", password_hash="hash_colab"
    )
    db.session.add(otro_usuario)
    db.session.commit()

    pregunta = publicar_pregunta(
        titulo="¿Cómo identificar autores en Flask?",
        cuerpo="Queremos distinguir al autor de la pregunta y a otros usuarios.",
        categoria_nombre="Arquitectura",
        nombres_tags=["autores"],
        usuario=usuario,
    )

    resp_autor = publicar_respuesta(
        pregunta_id=pregunta.id,
        cuerpo="Esta respuesta la escribe el mismo creador de la pregunta.",
        usuario=usuario,
    )
    resp_otro = publicar_respuesta(
        pregunta_id=pregunta.id,
        cuerpo="Esta respuesta la aporta otro miembro de la comunidad.",
        usuario=otro_usuario,
    )

    assert resp_autor.autor_nombre == "usuario_test"
    assert resp_autor.es_autor_pregunta is True
    assert resp_autor.es_ia is False

    assert resp_otro.autor_nombre == "colaborador"
    assert resp_otro.es_autor_pregunta is False
    assert resp_otro.es_ia is False


def test_identificacion_autor_ia(app, usuario):
    pregunta = publicar_pregunta(
        titulo="¿Cómo etiquetar respuestas generadas por IA?",
        cuerpo="Necesitamos identificar cuando una respuesta proviene de un modelo de IA.",
        categoria_nombre="IA",
        nombres_tags=["ia"],
        usuario=usuario,
    )

    resp_ia = Respuesta(
        cuerpo="Respuesta generada automáticamente.",
        pregunta=pregunta,
        usuario=usuario,
        es_ia=True,
        modelo_ia="Gemini 2.5",
    )
    db.session.add(resp_ia)
    db.session.commit()

    assert resp_ia.autor_nombre == "Gemini 2.5"
    assert resp_ia.es_autor_pregunta is False


def test_aceptar_respuesta_exitosa(app, usuario):
    otro_usuario = Usuario(
        username="colaborador",
        email="colab@test.com",
        password_hash="hash_colab",
    )
    db.session.add(otro_usuario)
    db.session.commit()

    pregunta = publicar_pregunta(
        titulo="¿Cómo funciona la aceptación?",
        cuerpo="Quiero probar cómo aceptar una respuesta de otro usuario.",
        categoria_nombre="Testing",
        nombres_tags=["aceptacion"],
        usuario=usuario,
    )

    respuesta = publicar_respuesta(
        pregunta_id=pregunta.id,
        cuerpo="Esta es una respuesta de la comunidad.",
        usuario=otro_usuario,
    )

    aceptada = aceptar_respuesta(
        respuesta_id=respuesta.id,
        usuario=usuario,
    )

    assert aceptada.estado == EstadoRespuesta.ACEPTADA.value


def test_aceptar_respuesta_otro_usuario_falla(app, usuario):
    otro_usuario = Usuario(
        username="intruso",
        email="intruso@test.com",
        password_hash="hash_intruso",
    )
    db.session.add(otro_usuario)
    db.session.commit()

    pregunta = publicar_pregunta(
        titulo="¿Quién puede aceptar respuestas?",
        cuerpo="Solo el autor de la pregunta debería poder hacerlo.",
        categoria_nombre="Testing",
        nombres_tags=["permisos"],
        usuario=usuario,
    )

    respuesta = publicar_respuesta(
        pregunta_id=pregunta.id,
        cuerpo="Una respuesta de prueba válida.",
        usuario=otro_usuario,
    )

    with pytest.raises(PermissionError, match="Solo el autor"):
        aceptar_respuesta(
            respuesta_id=respuesta.id,
            usuario=otro_usuario,
        )


def test_aceptar_respuesta_inexistente(app, usuario):
    with pytest.raises(ValueError, match="no existe"):
        aceptar_respuesta(
            respuesta_id=9999,
            usuario=usuario,
        )


def test_aceptar_otra_respuesta_desmarca_la_anterior(app, usuario):
    otro_usuario = Usuario(
        username="colaborador",
        email="colab@test.com",
        password_hash="hash_colab",
    )
    db.session.add(otro_usuario)
    db.session.commit()

    pregunta = publicar_pregunta(
        titulo="¿Cómo cambiar una respuesta aceptada?",
        cuerpo="Probando aceptar una segunda respuesta en la misma pregunta.",
        categoria_nombre="Testing",
        nombres_tags=["aceptacion"],
        usuario=usuario,
    )

    respuesta_1 = publicar_respuesta(
        pregunta_id=pregunta.id,
        cuerpo="Primera respuesta de prueba.",
        usuario=otro_usuario,
    )

    respuesta_2 = publicar_respuesta(
        pregunta_id=pregunta.id,
        cuerpo="Segunda respuesta de prueba.",
        usuario=otro_usuario,
    )

    aceptar_respuesta(respuesta_1.id, usuario)
    aceptar_respuesta(respuesta_2.id, usuario)

    assert respuesta_1.estado == EstadoRespuesta.ACEPTADA.value
    assert respuesta_2.estado == EstadoRespuesta.ACEPTADA.value


def test_aceptar_respuesta_no_modifica_otra_pregunta(app, usuario):
    otro_usuario = Usuario(
        username="colaborador",
        email="colab@test.com",
        password_hash="hash_colab",
    )
    db.session.add(otro_usuario)
    db.session.commit()

    pregunta_1 = publicar_pregunta(
        titulo="¿Cómo funcionan las relaciones?",
        cuerpo="Primera pregunta para probar la aceptación.",
        categoria_nombre="Python",
        nombres_tags=["relaciones"],
        usuario=usuario,
    )

    pregunta_2 = publicar_pregunta(
        titulo="¿Cómo funcionan las consultas?",
        cuerpo="Segunda pregunta para probar la aceptación.",
        categoria_nombre="Python",
        nombres_tags=["consultas"],
        usuario=usuario,
    )

    respuesta_1 = publicar_respuesta(
        pregunta_id=pregunta_1.id,
        cuerpo="Respuesta correspondiente a la primera pregunta.",
        usuario=otro_usuario,
    )

    respuesta_2 = publicar_respuesta(
        pregunta_id=pregunta_2.id,
        cuerpo="Respuesta correspondiente a la segunda pregunta.",
        usuario=otro_usuario,
    )

    aceptar_respuesta(respuesta_1.id, usuario)
    aceptar_respuesta(respuesta_2.id, usuario)

    assert respuesta_1.estado == EstadoRespuesta.ACEPTADA.value
    assert respuesta_2.estado == EstadoRespuesta.ACEPTADA.value


##Pruebas


def test_ruta_editar_respuesta_requiere_login(app, usuario, client):
    pregunta = publicar_pregunta(
        titulo="¿Cómo probar la edición?",
        cuerpo="Pregunta para probar la autenticación.",
        categoria_nombre="Testing",
        nombres_tags=["pytest"],
        usuario=usuario,
    )
    respuesta = publicar_respuesta(
        pregunta_id=pregunta.id,
        cuerpo="Respuesta original.",
        usuario=usuario,
    )

    response = client.post(
        f"/answers/{respuesta.id}/edit",
        data={"cuerpo": "Intento sin sesión."},
    )

    assert response.status_code == 401


def test_ruta_editar_respuesta_no_permite_otro_usuario(app, usuario, cliente_autenticado):
    otro_usuario = Usuario(
        username="intruso",
        email="intruso@test.com",
        password_hash="hash_intruso",
    )
    db.session.add(otro_usuario)
    db.session.commit()

    pregunta = publicar_pregunta(
        titulo="¿Quién puede editar?",
        cuerpo="Pregunta para probar los permisos.",
        categoria_nombre="Testing",
        nombres_tags=["permisos"],
        usuario=usuario,
    )
    respuesta = publicar_respuesta(
        pregunta_id=pregunta.id,
        cuerpo="Respuesta del autor original.",
        usuario=usuario,
    )

    cliente = cliente_autenticado(otro_usuario)
    response = cliente.post(
        f"/answers/{respuesta.id}/edit",
        data={"cuerpo": "Intento de modificación."},
    )

    assert response.status_code == 403
    assert respuesta.cuerpo == "Respuesta del autor original."


def test_ruta_editar_respuesta_exitosa(app, usuario, cliente_autenticado):
    pregunta = publicar_pregunta(
        titulo="¿Cómo actualizar una respuesta?",
        cuerpo="Pregunta para probar la ruta de edición.",
        categoria_nombre="Testing",
        nombres_tags=["edicion"],
        usuario=usuario,
    )
    respuesta = publicar_respuesta(
        pregunta_id=pregunta.id,
        cuerpo="Texto original.",
        usuario=usuario,
    )

    cliente = cliente_autenticado(usuario)
    response = cliente.post(
        f"/answers/{respuesta.id}/edit",
        data={"cuerpo": "Texto actualizado desde la ruta."},
    )

    assert response.status_code == 302
    assert respuesta.cuerpo == "Texto actualizado desde la ruta."
    assert respuesta.fecha_edicion is not None


def test_ruta_editar_respuesta_inexistente(app, usuario, cliente_autenticado):
    cliente = cliente_autenticado(usuario)

    response = cliente.post(
        "/answers/9999/edit",
        data={"cuerpo": "Respuesta que no existe."},
    )

    assert response.status_code == 404

def test_eliminar_respuesta_autor_exitosa(app, usuario):
    from compilando.modules.answers.services import eliminar_respuesta

    pregunta = publicar_pregunta(
        titulo="¿Cómo borrar mi propia respuesta?",
        cuerpo="Probando eliminación de respuesta propia.",
        categoria_nombre="Python",
        nombres_tags=["pytest"],
        usuario=usuario,
    )
    respuesta = publicar_respuesta(
        pregunta_id=pregunta.id,
        cuerpo="Esta es mi respuesta para eliminar.",
        usuario=usuario,
    )

    pregunta_id = eliminar_respuesta(respuesta_id=respuesta.id, usuario=usuario)

    assert pregunta_id == pregunta.id
    assert db.session.get(Respuesta, respuesta.id) is None


def test_eliminar_respuesta_otro_usuario_falla(app, usuario):
    from compilando.modules.answers.services import eliminar_respuesta

    intruso = Usuario(
        username="intruso_resp",
        email="intruso_resp@test.com",
        password_hash="hash_intruso",
    )
    db.session.add(intruso)
    db.session.commit()

    pregunta = publicar_pregunta(
        titulo="¿Puede otro usuario borrar mi respuesta?",
        cuerpo="Solo el autor de la respuesta debería poder eliminarla.",
        categoria_nombre="Seguridad",
        nombres_tags=["permisos"],
        usuario=usuario,
    )
    respuesta = publicar_respuesta(
        pregunta_id=pregunta.id,
        cuerpo="Respuesta protegida contra terceros.",
        usuario=usuario,
    )

    with pytest.raises(PermissionError, match="Solo el autor"):
        eliminar_respuesta(respuesta_id=respuesta.id, usuario=intruso)


def test_ruta_eliminar_respuesta(app, usuario, client, cliente_autenticado):
    pregunta = publicar_pregunta(
        titulo="¿Ruta POST para eliminar respuesta?",
        cuerpo="Probando endpoint HTTP de eliminación de respuesta.",
        categoria_nombre="Flask",
        nombres_tags=["rutas"],
        usuario=usuario,
    )
    respuesta = publicar_respuesta(
        pregunta_id=pregunta.id,
        cuerpo="Respuesta que será eliminada vía HTTP POST.",
        usuario=usuario,
    )

    resp_anon = client.post(f"/answers/{respuesta.id}/delete")
    assert resp_anon.status_code == 401

    auth_client = cliente_autenticado(usuario)
    resp_ok = auth_client.post(f"/answers/{respuesta.id}/delete", follow_redirects=False)
    assert resp_ok.status_code == 302
    assert db.session.get(Respuesta, respuesta.id) is None
