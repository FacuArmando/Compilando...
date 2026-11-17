"""Rutas iniciales disponibles en esta entrega."""

from flask import Blueprint, render_template
from sqlalchemy import select

from compilando.extensions import db
from compilando.modules.questions.models import Pregunta

bp = Blueprint("system", __name__)


@bp.get("/")
def index():
    preguntas = db.session.scalars(select(Pregunta).order_by(Pregunta.id.desc())).all()
    return render_template("system/index.html", preguntas=preguntas)


@bp.get("/health")
def health():
    """Indicar que el proceso web responde; no evalúa servicios externos."""
    return {"status": "ok", "application": "compilando"}
