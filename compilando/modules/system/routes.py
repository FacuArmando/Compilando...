"""Rutas iniciales disponibles en esta entrega."""

from flask import Blueprint, render_template

bp = Blueprint("system", __name__)


@bp.get("/")
def index():
    return render_template("system/index.html")


@bp.get("/health")
def health():
    """Indicar que el proceso web responde; no evalúa servicios externos."""
    return {"status": "ok", "application": "compilando"}
