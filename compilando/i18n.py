"""Interfaz ES/EN explícita: nunca traduce contenido de la comunidad."""

import json
import re
from datetime import datetime
from pathlib import Path

from flask import Response, has_request_context, request
from markupsafe import Markup, escape

CATALOG = json.loads(
    Path(__file__).with_name("translations").joinpath("en.json").read_text(encoding="utf-8")
)
COOKIE = "compilando-language"


def language():
    """Ignorar idiomas desconocidos, sin cambiar la sesión de autenticación."""
    return "en" if has_request_context() and request.cookies.get(COOKIE) == "en" else "es"


def message_parts(message, params):
    """Recuperar parámetros de errores del servidor que ya llegan formateados."""
    message = str(message or "")
    if message in CATALOG or params:
        return message, params
    for key in sorted(CATALOG, key=lambda text: len(re.sub(r"\{\w+\}", "", text)), reverse=True):
        names = re.findall(r"\{(\w+)\}", key)
        if not names:
            continue
        pattern = re.escape(key)
        for name in names:
            pattern = pattern.replace(re.escape("{" + name + "}"), f"(?P<{name}>.+?)", 1)
        if match := re.fullmatch(pattern, message):
            return key, match.groupdict()
    return message, params


def tr(message, **params):
    key, params = message_parts(message, params)
    template = CATALOG.get(key, key) if language() == "en" else key
    # Solo interpolar plantillas conocidas. Las llaves en errores ajenos son texto.
    return template.format_map(params) if params else template


def ui(message, **params):
    """Marcar únicamente texto de interfaz para el cambio de idioma en vivo."""
    key, params = message_parts(message, params)
    if not key:
        return ""
    return Markup('<span data-i18n="{}" data-i18n-params="{}">{}</span>').format(
        escape(key), escape(json.dumps(params, ensure_ascii=False)), escape(tr(key, **params))
    )


def i18n_attr(attr, message, **params):
    if attr not in {"aria-label", "placeholder", "title"}:
        raise ValueError("Atributo no permitido para traducción")
    return Markup('{}="{}" data-i18n-{}="{}" data-i18n-{}-params="{}"').format(
        attr,
        escape(tr(message, **params)),
        attr,
        escape(message),
        attr,
        escape(json.dumps(params, ensure_ascii=False)),
    )


def ui_date(value: datetime, *, detailed=False):
    if detailed and language() == "es":
        from compilando.modules.answers.models import _formatear_fecha_es

        text = _formatear_fecha_es(value)
    elif detailed:
        text = value.strftime("%a, %d %b %Y, %H:%M")
    else:
        text = value.strftime("%d/%m/%Y" if language() == "es" else "%b %d, %Y")
    return Markup('<time datetime="{}" data-i18n-date="{}" data-date-style="{}">{}</time>').format(
        value.isoformat(), value.isoformat(), "long" if detailed else "short", escape(text)
    )


def init_app(app):
    app.jinja_env.globals.update(tr=tr, ui=ui, i18n_attr=i18n_attr, ui_date=ui_date)

    @app.get("/interface-catalog.js")
    def interface_catalog():
        return Response(
            "window.CompilandoCatalog=" + json.dumps(CATALOG) + ";",
            mimetype="text/javascript",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    @app.context_processor
    def locale_context():
        return {"current_language": language()}
