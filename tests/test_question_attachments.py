"""Publicación real, acceso público y persistencia consistente de archivos de código."""

import io
import re
from pathlib import Path
from unittest.mock import Mock

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect, select
from werkzeug.datastructures import FileStorage

from compilando import create_app
from compilando.extensions import db
from compilando.modules.auth.services import registrar_usuario
from compilando.modules.questions.models import AdjuntoPregunta, Pregunta
from compilando.modules.questions.services import publicar_pregunta


@pytest.fixture
def app_adjuntos(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "clave-exclusiva-para-probar-archivos-123456789",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'preguntas.sqlite'}",
            "QUESTION_UPLOAD_FOLDER": str(tmp_path / "adjuntos"),
        }
    )
    with app.app_context():
        db.create_all()
        registrar_usuario("Mati", "mati@example.test", "clave-prueba")
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def csrf(response):
    return re.search(r'name="csrf_token"\s+value="([^"]+)"', response.get_data(as_text=True))[1]


@pytest.fixture
def cliente_adjuntos(app_adjuntos):
    cliente = app_adjuntos.test_client()
    response = cliente.post(
        "/auth/login",
        data={
            "csrf_token": csrf(cliente.get("/auth/login")),
            "email": "mati@example.test",
            "password": "clave-prueba",
        },
    )
    assert response.status_code == 303
    return cliente


def publicar(cliente, archivos=(), *, tipo_mime=None, **campos):
    data = {
        "csrf_token": csrf(cliente.get("/questions/publish")),
        "titulo": "¿Cómo implemento la interfaz?",
        "cuerpo": "Quiero compartir mi código para entender la herencia.",
        "categoria": "Java",
        "tags": "interfaces, herencia",
        "archivos": [
            (io.BytesIO(contenido), nombre, tipo_mime)
            if tipo_mime
            else (io.BytesIO(contenido), nombre)
            for nombre, contenido in archivos
        ],
    }
    data.update(campos)
    return cliente.post("/questions/publish", data=data, content_type="multipart/form-data")


def guardados(app):
    with app.app_context():
        return db.session.scalars(select(AdjuntoPregunta).order_by(AdjuntoPregunta.orden)).all()


def assert_sin_publicacion(app):
    with app.app_context():
        assert db.session.scalar(select(db.func.count()).select_from(Pregunta)) == 0
        assert db.session.scalar(select(db.func.count()).select_from(AdjuntoPregunta)) == 0
    assert list(Path(app.config["QUESTION_UPLOAD_FOLDER"]).glob("*")) == []


def test_tres_clases_se_guardan_en_orden_y_se_leen_y_descargan_sin_alteraciones(
    app_adjuntos, cliente_adjuntos
):
    archivos = [
        ("Animal.java", b"public abstract class Animal {\r\n\tabstract void hablar();\r\n}\r\n"),
        ("Mascota.java", "public interface Mascota {\n    // compañía\n}\n".encode()),
        (
            "Perro.java",
            b"// Este codigo tiene errores: eso es lo que quiero consultar\nclass Perro",
        ),
    ]
    response = publicar(cliente_adjuntos, archivos)
    assert response.status_code == 302
    pregunta_url = response.headers["Location"]
    visitante = app_adjuntos.test_client()
    pagina = visitante.get(pregunta_url)
    assert pagina.status_code == 200
    adjuntos = guardados(app_adjuntos)
    assert [a.nombre_original for a in adjuntos] == [nombre for nombre, _ in archivos]
    assert [a.orden for a in adjuntos] == [0, 1, 2]
    carpeta = Path(app_adjuntos.config["QUESTION_UPLOAD_FOLDER"])
    assert sorted(p.name for p in carpeta.iterdir()) == sorted(a.id for a in adjuntos)
    for adjunto, (nombre, contenido) in zip(adjuntos, archivos, strict=True):
        assert nombre.encode() in pagina.data
        ruta = f"{pregunta_url}/attachments/{adjunto.id}"
        vista = visitante.get(ruta)
        descarga = visitante.get(f"{ruta}/download")
        assert vista.status_code == descarga.status_code == 200
        assert b"<pre" in vista.data
        assert descarga.data == contenido
        assert descarga.mimetype == "application/octet-stream"
        assert descarga.headers["Content-Disposition"].startswith("attachment;")
        assert nombre in descarga.headers["Content-Disposition"]
        assert descarga.headers["X-Content-Type-Options"] == "nosniff"
        assert visitante.get(f"/static/question-attachments/{adjunto.id}").status_code == 404


def test_publicar_sin_adjuntos_conserva_el_formulario_original(app_adjuntos, cliente_adjuntos):
    response = publicar(cliente_adjuntos)
    assert response.status_code == 302
    pagina = cliente_adjuntos.get(response.headers["Location"])
    assert pagina.status_code == 200
    assert b"Archivos adjuntos" not in pagina.data
    assert guardados(app_adjuntos) == []


def test_mismo_nombre_no_sobrescribe_y_las_rutas_recibidas_no_se_usan(
    app_adjuntos, cliente_adjuntos
):
    response = publicar(
        cliente_adjuntos,
        # El generador multipart de Werkzeug desescapa las barras del encabezado.
        [("../../Clase.java", b"class Primera {}"), (r"C:\\equipo\\Clase.java", b"class Otra {}")],
    )
    assert response.status_code == 302
    adjuntos = guardados(app_adjuntos)
    assert [a.nombre_original for a in adjuntos] == ["Clase.java", "Clase.java"]
    assert adjuntos[0].id != adjuntos[1].id
    carpeta = Path(app_adjuntos.config["QUESTION_UPLOAD_FOLDER"])
    assert (carpeta / adjuntos[0].id).read_bytes() == b"class Primera {}"
    assert (carpeta / adjuntos[1].id).read_bytes() == b"class Otra {}"


def test_nombre_y_codigo_se_muestran_como_texto_sin_ejecutar_html(app_adjuntos, cliente_adjuntos):
    nombre = "<script>.java"
    contenido = b'<script>alert("codigo")</script>\n'
    response = publicar(cliente_adjuntos, [(nombre, contenido)])
    assert response.status_code == 302
    adjunto = guardados(app_adjuntos)[0]
    detalle = cliente_adjuntos.get(response.headers["Location"])
    vista = cliente_adjuntos.get(f"/questions/{adjunto.pregunta_id}/attachments/{adjunto.id}")
    assert b"<script>.java" not in detalle.data
    assert b"&lt;script&gt;.java" in detalle.data
    assert b'<script>alert("codigo")</script>' not in vista.data
    assert b"&lt;script&gt;" in vista.data


@pytest.mark.parametrize(
    ("archivos", "mensaje"),
    [
        ([(f"Clase{i}.java", b"class Clase {}") for i in range(11)], "hasta 10"),
        ([("Clase.java", b"a" * (1024 * 1024 + 1))], "por archivo"),
        ([(f"C{i}.java", b"a" * (5 * 1024 * 1024 // 6 + 1)) for i in range(6)], "total"),
        ([("Clase.java.exe", b"texto")], "tipos"),
        ([(".env", b"SECRET=valor")], "tipos"),
        ([("Proyecto.zip", b"PK")], "tipos"),
        ([("Clase.java", b"\x00\x01ejecutable")], "binarios"),
        ([("Clase.java", b"\xff\xfe")], "UTF-8"),
        ([("Clase.java", b"")], "vacío"),
        ([("a" * 121 + ".java", b"class Clase {}")], "120 caracteres"),
    ],
)
def test_rechaza_cargas_invalidas_sin_guardar_pregunta_ni_archivos(
    app_adjuntos, cliente_adjuntos, archivos, mensaje
):
    response = publicar(cliente_adjuntos, archivos)
    assert response.status_code == 400
    assert mensaje in response.get_data(as_text=True)
    assert "volvé a seleccionar" in response.get_data(as_text=True)
    assert_sin_publicacion(app_adjuntos)


def test_limites_exactos_de_cantidad_archivo_y_total_se_aceptan(app_adjuntos, cliente_adjuntos):
    limite = app_adjuntos.config["QUESTION_ATTACHMENT_MAX_BYTES"]
    # Diez archivos, uno exactamente de 1 MB, y el conjunto exactamente de 5 MB.
    tamanios = [limite] + [3 * limite // 8] * 8 + [limite]
    response = publicar(
        cliente_adjuntos, [(f"Clase{i}.java", b"x" * n) for i, n in enumerate(tamanios)]
    )
    assert response.status_code == 302
    assert len(guardados(app_adjuntos)) == 10
    assert sum(a.tamanio for a in guardados(app_adjuntos)) == 5 * limite


def test_error_en_campos_conserva_texto_y_no_guarda_archivos(app_adjuntos, cliente_adjuntos):
    response = publicar(cliente_adjuntos, [("Clase.java", b"class Clase {}")], titulo="corto")
    assert response.status_code == 200
    assert b'value="corto"' in response.data
    assert "volvé a seleccionar" in response.get_data(as_text=True)
    assert_sin_publicacion(app_adjuntos)


def test_exige_sesion_y_csrf_para_subir(app_adjuntos, cliente_adjuntos):
    visitante = app_adjuntos.test_client()
    token = csrf(visitante.get("/auth/login"))
    response = visitante.post(
        "/questions/publish",
        data={"csrf_token": token, "archivos": (io.BytesIO(b"class Clase {}"), "Clase.java")},
    )
    assert response.status_code == 401
    for token in ("", "inventado"):
        response = publicar(cliente_adjuntos, [("Clase.java", b"class Clase {}")], csrf_token=token)
        assert response.status_code == 400
    assert_sin_publicacion(app_adjuntos)


def test_request_demasiado_grande_devuelve_aviso_sin_archivos_parciales(
    app_adjuntos, cliente_adjuntos
):
    response = publicar(cliente_adjuntos, [("Clase.java", b"x" * (6 * 1024 * 1024))])
    assert response.status_code == 413
    assert "La carga es demasiado grande" in response.get_data(as_text=True)
    assert_sin_publicacion(app_adjuntos)


def test_adjunto_ajeno_a_la_pregunta_o_inexistente_devuelve_404(app_adjuntos, cliente_adjuntos):
    response = publicar(cliente_adjuntos, [("Clase.java", b"class Clase {}")])
    assert response.status_code == 302
    adjunto = guardados(app_adjuntos)[0]
    for sufijo in ("", "/download"):
        for ruta in (
            f"/questions/999/attachments/{adjunto.id}{sufijo}",
            f"/questions/{adjunto.pregunta_id}/attachments/inexistente{sufijo}",
        ):
            assert cliente_adjuntos.get(ruta).status_code == 404
    Path(app_adjuntos.config["QUESTION_UPLOAD_FOLDER"], adjunto.id).unlink()
    ruta = f"/questions/{adjunto.pregunta_id}/attachments/{adjunto.id}"
    assert cliente_adjuntos.get(ruta).status_code == 404
    assert cliente_adjuntos.get(f"{ruta}/download").status_code == 404


@pytest.mark.parametrize("fallo", ["segundo_archivo", "commit"])
def test_fallo_al_guardar_revierte_la_pregunta_y_elimina_archivos_parciales(
    app_adjuntos, monkeypatch, fallo
):
    from compilando.modules.auth.models import Usuario
    from compilando.modules.questions import services

    with app_adjuntos.app_context():
        usuario = db.session.scalar(select(Usuario))
        archivos = [
            FileStorage(io.BytesIO(b"class Clase {}"), filename=f"C{i}.java") for i in range(2)
        ]
        if fallo == "segundo_archivo":
            guardar = services.guardar_adjunto

            def guardar_con_fallo(archivo, orden):
                if orden == 1:
                    raise OSError("Sin espacio")
                return guardar(archivo, orden)

            monkeypatch.setattr(services, "guardar_adjunto", guardar_con_fallo)
        else:
            monkeypatch.setattr(db.session, "commit", Mock(side_effect=OSError("Fallo simulado")))
        with pytest.raises(OSError):
            publicar_pregunta(
                "Pregunta válida", "Mi código", "Java", [], usuario, archivos=archivos
            )
    assert_sin_publicacion(app_adjuntos)


def test_migracion_nueva_conserva_preguntas_y_se_puede_revertir_en_base_temporal(tmp_path):
    app = create_app(
        {"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'migracion.sqlite'}"}
    )
    with app.app_context():
        upgrade(revision="4b2e88c7eeba")
        usuario = registrar_usuario("Mati", "mati@example.test", "clave-prueba")
        pregunta = publicar_pregunta("Pregunta previa", "Mi código", "Java", [], usuario)
        pregunta_id = pregunta.id
        db.session.remove()
        upgrade()
        assert "adjuntos_pregunta" in inspect(db.engine).get_table_names()
        assert db.session.get(Pregunta, pregunta_id).titulo == "Pregunta previa"
        db.session.remove()
        downgrade(revision="4b2e88c7eeba")
        assert "adjuntos_pregunta" not in inspect(db.engine).get_table_names()
        assert db.session.get(Pregunta, pregunta_id).titulo == "Pregunta previa"
        db.session.remove()
        db.engine.dispose()


# #21: validación independiente de los controles del navegador.
@pytest.mark.parametrize(
    ("nombre", "contenido", "mensaje"),
    [
        ("", b"class SinNombre {}", "no tiene nombre"),
        ("Archivo\u202eavaj.java", b"class Prueba {}", "invisibles"),
        ("Archivo\u200b.java", b"class Prueba {}", "invisibles"),
        ("Archivo\x00.java", b"class Prueba {}", "control"),
        ("Vacio.java", b"\xef\xbb\xbf", "vacío"),
        ("Clase.java", b"MZ\x00programa", "binarios"),
        ("Clase.java", b"PK\x03\x04archivo", "binarios"),
        ("Clase.java", "texto\u0085control".encode(), "binarios"),
        ("Clase.java", b"\xc0\xaf", "UTF-8"),
        ("Clase.java", b"\xed\xa0\x80", "UTF-8"),
    ],
)
def test_validacion_rechaza_cargas_manipuladas_sin_aceptar_el_primer_archivo(
    app_adjuntos, cliente_adjuntos, nombre, contenido, mensaje
):
    response = publicar(
        cliente_adjuntos,
        [("Correcto.java", b"class Correcto {}"), (nombre, contenido)],
        tipo_mime="text/plain",
    )
    assert response.status_code == 400
    assert mensaje in response.get_data(as_text=True)
    assert b"interfaces, herencia" in response.data
    assert_sin_publicacion(app_adjuntos)


@pytest.mark.parametrize("extension", [".java", ".JAVA", ".py", ".js", ".jsx", ".txt"])
def test_formatos_permitidos_aceptan_unicode_y_bom_y_conservan_el_original(
    app_adjuntos, cliente_adjuntos, extension
):
    nombre = "Árbol" + extension
    contenido = b"\xef\xbb\xbf" + "// año y árbol\r\n\tfunción sin terminar\n".encode()
    response = publicar(
        cliente_adjuntos, [(nombre, contenido)], tipo_mime="application/octet-stream"
    )
    assert response.status_code == 302
    adjunto = guardados(app_adjuntos)[0]
    assert adjunto.nombre_original == nombre
    ruta = f"/questions/{adjunto.pregunta_id}/attachments/{adjunto.id}"
    assert "año y árbol" in cliente_adjuntos.get(ruta).get_data(as_text=True)
    assert cliente_adjuntos.get(ruta + "/download").data == contenido


def test_ignora_el_selector_vacio_pero_no_un_archivo_sin_nombre(app_adjuntos, cliente_adjuntos):
    response = publicar(cliente_adjuntos, [("", b"")])
    assert response.status_code == 302
    assert guardados(app_adjuntos) == []


def test_un_archivo_en_otro_campo_no_se_ignora_silenciosamente(app_adjuntos, cliente_adjuntos):
    response = publicar(
        cliente_adjuntos,
        [("Correcto.java", b"class Correcto {}")],
        otro_archivo=(io.BytesIO(b"class Oculto {}"), "Oculto.java"),
    )
    assert response.status_code == 400
    assert "selector de adjuntos" in response.get_data(as_text=True)
    assert_sin_publicacion(app_adjuntos)


def test_nombre_en_el_limite_cuenta_caracteres_unicode_y_no_bytes(app_adjuntos, cliente_adjuntos):
    nombre = "😀" * 115 + ".java"
    response = publicar(cliente_adjuntos, [(nombre, b"class Emoji {}")])
    assert response.status_code == 302
    assert guardados(app_adjuntos)[0].nombre_original == nombre


@pytest.mark.parametrize(
    ("archivos", "mensaje"),
    [
        ([("Clase.java", b"x" * 257)], "256 B por archivo"),
        ([(f"C{i}.java", b"x" * 200) for i in range(3)], "total de 512 B"),
    ],
)
def test_configuracion_de_limites_se_aplica_y_aparece_en_el_error(
    app_adjuntos, cliente_adjuntos, archivos, mensaje
):
    app_adjuntos.config.update(
        QUESTION_ATTACHMENT_MAX_BYTES=256, QUESTION_ATTACHMENT_TOTAL_BYTES=512
    )
    response = publicar(cliente_adjuntos, archivos)
    assert response.status_code == 400
    assert mensaje in response.get_data(as_text=True)
    assert_sin_publicacion(app_adjuntos)


@pytest.mark.parametrize("exceso", ["partes", "campo"])
def test_limites_del_multipart_tambien_se_exigen_en_el_servidor(
    app_adjuntos, cliente_adjuntos, exceso
):
    campos = (
        {f"extra{i}": "texto" for i in range(14)}
        if exceso == "partes"
        else {"cuerpo": "x" * (64 * 1024 + 1)}
    )
    response = publicar(cliente_adjuntos, [("Clase.java", b"class Clase {}")], **campos)
    assert response.status_code == 413
    assert "10 archivos" in response.get_data(as_text=True)
    assert_sin_publicacion(app_adjuntos)
