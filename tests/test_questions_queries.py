from compilando.modules.questions.services import publicar_pregunta


def test_consultar_preguntas_publicadas(app, usuario):
    publicar_pregunta(
        titulo="¿Cómo funciona Python?",
        cuerpo="Quiero aprender los fundamentos de este lenguaje.",
        categoria_nombre="Programación",
        nombres_tags=["python"],
        usuario=usuario,
    )

    publicar_pregunta(
        titulo="¿Cómo funciona Flask?",
        cuerpo="Quiero aprender a desarrollar aplicaciones web.",
        categoria_nombre="Desarrollo web",
        nombres_tags=["flask"],
        usuario=usuario,
    )

    cliente = app.test_client()
    response = cliente.get("/")

    assert response.status_code == 200
    assert b"Preguntas recientes" in response.data
    assert (
        b"Como funciona Python?" in response.data
        or "¿Cómo funciona Python?".encode() in response.data
    )
    assert "¿Cómo funciona Flask?".encode() in response.data

    posicion_flask = response.data.index("¿Cómo funciona Flask?".encode())
    posicion_python = response.data.index("¿Cómo funciona Python?".encode())

    assert posicion_flask < posicion_python


def test_consultar_preguntas_sin_publicaciones(app):
    cliente = app.test_client()
    response = cliente.get("/")

    assert response.status_code == 200
    assert "Todavía no hay preguntas publicadas.".encode() in response.data
