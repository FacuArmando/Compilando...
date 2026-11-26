"""Recepción y almacenamiento de código fuente, sin ejecutarlo ni compilarlo."""

from dataclasses import dataclass
from pathlib import Path
from unicodedata import category
from uuid import uuid4

from flask import abort, current_app, request
from werkzeug.datastructures import FileStorage

from compilando.modules.questions.models import AdjuntoPregunta
from compilando.storage import guardar_blob, leer_blob, usa_base

MAX_NOMBRE_ADJUNTO = 120


class AdjuntosInvalidos(ValueError):
    """El usuario debe corregir los archivos antes de publicar."""


@dataclass(frozen=True)
class ArchivoPreparado:
    nombre: str
    contenido: bytes


def opciones_adjuntos() -> dict:
    config = current_app.config
    return {
        "cantidad": config["QUESTION_ATTACHMENT_MAX_FILES"],
        "por_archivo": config["QUESTION_ATTACHMENT_MAX_BYTES"],
        "total": config["QUESTION_ATTACHMENT_TOTAL_BYTES"],
        "extensiones": config["QUESTION_ATTACHMENT_EXTENSIONS"],
        "nombre_maximo": MAX_NOMBRE_ADJUNTO,
    }


def tamanio_legible(cantidad: int) -> str:
    for unidad, divisor in (("MB", 1024 * 1024), ("KB", 1024)):
        if cantidad >= divisor:
            return f"{cantidad / divisor:g} {unidad}"
    return f"{cantidad} B"


def preparar_adjuntos(archivos: list[FileStorage]) -> list[ArchivoPreparado]:
    """Validar todo antes de escribir; no confiar en el tipo enviado por el navegador."""
    limites = opciones_adjuntos()
    seleccionados = []
    for archivo in archivos:
        if archivo.filename:
            seleccionados.append(archivo)
        elif archivo.stream.read(1):
            raise AdjuntosInvalidos("Uno de los archivos no tiene nombre. Volvé a seleccionarlo.")
        # El selector nativo vacío envía filename="" y cero bytes: no es un adjunto.
    archivos = seleccionados
    if len(archivos) > limites["cantidad"]:
        raise AdjuntosInvalidos(f"Podés adjuntar hasta {limites['cantidad']} archivos.")

    preparados = []
    total = 0
    for archivo in archivos:
        # Un nombre recibido nunca se usa como ruta de almacenamiento.
        nombre = archivo.filename.replace("\\", "/").rsplit("/", 1)[-1]
        if (
            not nombre
            or len(nombre) > limites["nombre_maximo"]
            or any(category(c) in {"Cc", "Cf"} for c in nombre)
        ):
            raise AdjuntosInvalidos(
                f"Usá nombres de archivo de hasta {limites['nombre_maximo']} caracteres, "
                "sin caracteres invisibles o de control."
            )
        if Path(nombre).suffix.lower() not in limites["extensiones"]:
            permitidos = ", ".join(limites["extensiones"])
            raise AdjuntosInvalidos(f"{nombre}: elegí un archivo de estos tipos: {permitidos}.")
        contenido = archivo.stream.read(limites["por_archivo"] + 1)
        if len(contenido) > limites["por_archivo"]:
            maximo = tamanio_legible(limites["por_archivo"])
            raise AdjuntosInvalidos(f"{nombre}: supera el máximo de {maximo} por archivo.")
        total += len(contenido)
        if total > limites["total"]:
            maximo = tamanio_legible(limites["total"])
            raise AdjuntosInvalidos(f"Los archivos juntos superan el límite total de {maximo}.")
        if not contenido:
            raise AdjuntosInvalidos(f"{nombre}: el archivo está vacío.")
        try:
            texto = contenido.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise AdjuntosInvalidos(f"{nombre}: guardá el archivo como texto UTF-8.") from None
        if not texto:
            raise AdjuntosInvalidos(f"{nombre}: el archivo está vacío.")
        if any(category(c) == "Cc" and c not in "\t\r\n" for c in texto):
            raise AdjuntosInvalidos(f"{nombre}: debe contener texto, sin datos binarios.")
        preparados.append(ArchivoPreparado(nombre, contenido))
    return preparados


def ruta_adjunto(identificador: str) -> Path:
    return Path(current_app.config["QUESTION_UPLOAD_FOLDER"]).resolve() / identificador


def guardar_adjunto(
    archivo: ArchivoPreparado, orden: int, *, pregunta_id: int | None = None
) -> AdjuntoPregunta:
    identificador = uuid4().hex
    if usa_base():
        guardar_blob("attachments/" + identificador, archivo.contenido, pregunta_id=pregunta_id)
        return AdjuntoPregunta(
            id=identificador,
            nombre_original=archivo.nombre,
            tamanio=len(archivo.contenido),
            orden=orden,
        )
    ruta = ruta_adjunto(identificador)
    ruta.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # La creación exclusiva evita reemplazar un archivo, incluso ante una colisión.
    destino = ruta.open("xb")
    try:
        with destino:
            ruta.chmod(0o600)
            destino.write(archivo.contenido)
    except Exception:
        ruta.unlink(missing_ok=True)
        raise
    return AdjuntoPregunta(
        id=identificador,
        nombre_original=archivo.nombre,
        tamanio=len(archivo.contenido),
        orden=orden,
    )


def contenido_adjunto(adjunto: AdjuntoPregunta) -> bytes:
    try:
        if usa_base():
            contenido = leer_blob("attachments/" + adjunto.id)
        else:
            with ruta_adjunto(adjunto.id).open("rb") as origen:
                contenido = origen.read(current_app.config["QUESTION_ATTACHMENT_MAX_BYTES"] + 1)
        if contenido is None or len(contenido) != adjunto.tamanio:
            abort(404)
        return contenido
    except OSError:
        abort(404)


def leer_adjunto(adjunto: AdjuntoPregunta) -> str:
    try:
        return contenido_adjunto(adjunto).decode("utf-8-sig")
    except UnicodeDecodeError:
        abort(404)


def init_app(app) -> None:
    @app.before_request
    def limitar_carga_de_preguntas():
        if request.endpoint == "questions.publish_question":
            # Incluye los archivos, los campos del formulario y el envoltorio multipart.
            request.max_content_length = app.config["QUESTION_ATTACHMENT_TOTAL_BYTES"] + 128 * 1024
            request.max_form_memory_size = 64 * 1024
            request.max_form_parts = app.config["QUESTION_ATTACHMENT_MAX_FILES"] + 8
