"""Presupuestos de consultas para navegación sin datos privados ni red."""

from contextlib import contextmanager
from datetime import date

import pytest
from sqlalchemy import event

from compilando.extensions import db
from compilando.modules.answers.models import EstadoRespuesta, Respuesta
from compilando.modules.auth.models import Usuario
from compilando.modules.auth.services import obtener_estadisticas_usuario
from compilando.modules.categories.models import Categoria
from compilando.modules.questions.models import Pregunta
from compilando.modules.tags.models import Tag


@contextmanager
def reads(engine):
    statements = []

    def capture(conn, cursor, sql, params, context, many):
        if sql.lstrip().upper().startswith("SELECT"):
            statements.append(sql)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", capture)


@pytest.fixture
def populated(app, usuario, cliente_autenticado):
    others = [
        Usuario(username=f"lector{i}", email=f"lector{i}@example.test", password_hash="prueba")
        for i in range(2)
    ]
    category = Categoria(nombre="Python", descripcion="Pruebas")
    tags = [Tag(nombre="python"), Tag(nombre="objetos")]
    db.session.add_all(others + [category] + tags)
    usuario.bio = "Perfil de prueba"
    usuario.fecha_nacimiento = date(2000, 1, 1)
    for i in range(1, 26):
        question = Pregunta(
            titulo=f"Pregunta de prueba número {i}",
            cuerpo_detallado="Contenido.",
            usuario=usuario,
            categoria=category,
            tags=tags,
        )
        db.session.add(question)
        for author in [usuario, *others]:
            accepted = author is usuario and i % 2 == 0
            db.session.add(
                Respuesta(
                    cuerpo="Respuesta de prueba.",
                    pregunta=question,
                    usuario=author,
                    estado=(
                        EstadoRespuesta.ACEPTADA.value
                        if accepted
                        else EstadoRespuesta.NO_ACEPTADA.value
                    ),
                )
            )
    db.session.commit()
    uid = usuario.id
    qid = question.id
    client = cliente_autenticado(usuario)
    db.session.remove()
    return client, uid, qid


def test_estadisticas_correctas_en_una_lectura(app, populated):
    _, uid, _ = populated
    with reads(db.engine) as sql:
        result = obtener_estadisticas_usuario(uid)
    assert result == {
        "preguntas_realizadas": 25,
        "personas_respondieron": 2,
        "respuestas_aceptadas": 12,
        "respuestas_totales": 25,
        "porcentaje_aceptadas": 48,
    }
    assert len(sql) == 1


def test_perfil_carga_identidad_campos_y_estadisticas_en_dos_lecturas(app, populated):
    client, _, _ = populated
    with reads(db.engine) as sql:
        response = client.get("/auth/account")
    assert response.status_code == 200 and "Perfil de prueba" in response.text
    assert len(sql) <= 2


def test_inicio_con_conteos_y_veinte_tarjetas_en_tres_lecturas(app, populated):
    client, _, _ = populated
    with reads(db.engine) as sql:
        response = client.get("/")
    assert response.status_code == 200
    assert response.text.count('class="community-question"') == 20
    assert len(sql) <= 3


def test_detalle_no_hace_consultas_por_respuesta_ni_por_relacionada(app, populated):
    client, _, qid = populated
    with reads(db.engine) as sql:
        response = client.get(f"/questions/{qid}")
    assert response.status_code == 200 and "Respuesta de prueba." in response.text
    assert len(sql) <= 6
    assert any("LIMIT" in statement for statement in sql)


def test_avatar_publico_no_consulta_sesion_y_conserva_cache(
    app, usuario, cliente_autenticado, tmp_path
):
    app.config["AVATAR_UPLOAD_FOLDER"] = str(tmp_path)
    (tmp_path / "foto.png").write_bytes(b"imagen-de-prueba")
    client = cliente_autenticado(usuario)
    db.session.remove()
    with reads(db.engine) as sql:
        response = client.get("/auth/avatar/foto.png")
    assert response.status_code == 200 and response.data == b"imagen-de-prueba"
    assert sql == []
    assert response.headers["Cache-Control"] == "public, max-age=3600"
    assert "Cookie" not in response.headers.get("Vary", "")
