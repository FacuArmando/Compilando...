"""Los índices del listado se aplican sin perder publicaciones existentes."""

from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect, text

from compilando import create_app
from compilando.extensions import db
from compilando.modules.answers.models import EstadoRespuesta, Respuesta
from compilando.modules.auth.models import Usuario
from compilando.modules.categories.models import Categoria
from compilando.modules.questions.models import Pregunta


def test_indices_del_listado_conservan_preguntas_y_respuestas(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "clave-solo-para-pruebas",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'paginacion.sqlite'}",
        }
    )
    with app.app_context():
        upgrade(revision="c2a7f91e4d63")
        usuario = Usuario(username="autor", email="autor@example.com", password_hash="prueba")
        categoria = Categoria(nombre="Java", descripcion="Ejemplos de Java")
        db.session.add_all([usuario, categoria])
        db.session.flush()
        # Sembrar solo columnas de esa revisión histórica.
        pregunta_id = db.session.scalar(
            text(
                "INSERT INTO preguntas (titulo, cuerpo_detallado, fecha, usuario_id, categoria_id) "
                "VALUES (:titulo, :cuerpo, CURRENT_DATE, :usuario, :categoria) RETURNING id"
            ),
            {
                "titulo": "Cómo implementar una interfaz",
                "cuerpo": "Contenido previo.",
                "usuario": usuario.id,
                "categoria": categoria.id,
            },
        )
        respuesta = Respuesta(
            cuerpo="Definí el contrato en la interfaz.",
            pregunta_id=pregunta_id,
            usuario=usuario,
            estado=EstadoRespuesta.ACEPTADA.value,
        )
        db.session.add(respuesta)
        db.session.commit()
        respuesta_id = respuesta.id
        db.session.remove()

        esperados = {
            "preguntas": {
                "ix_preguntas_fecha_id": ["fecha", "id"],
                "ix_preguntas_categoria_fecha_id": ["categoria_id", "fecha", "id"],
            },
            "respuestas": {"ix_respuestas_pregunta_estado": ["pregunta_id", "estado"]},
        }
        try:
            for revision, presentes in [("head", True), ("be14a09c9a73", False), ("head", True)]:
                if presentes:
                    upgrade(revision=revision)
                else:
                    downgrade(revision=revision)
                inspector = inspect(db.engine)
                for tabla, indices in esperados.items():
                    encontrados = {
                        indice["name"]: indice["column_names"]
                        for indice in inspector.get_indexes(tabla)
                    }
                    for nombre, columnas in indices.items():
                        assert (nombre in encontrados) is presentes
                        if presentes:
                            assert encontrados[nombre] == columnas
                assert (
                    db.session.get(Pregunta, pregunta_id).titulo == "Cómo implementar una interfaz"
                )
                guardada = db.session.get(Respuesta, respuesta_id)
                assert guardada.cuerpo == "Definí el contrato en la interfaz."
                assert guardada.estado == EstadoRespuesta.ACEPTADA.value
                db.session.remove()
        finally:
            db.session.remove()
            db.engine.dispose()
