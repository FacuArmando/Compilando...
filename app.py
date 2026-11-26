"""Entrada WSGI detectada por Vercel; no migra ni escribe archivos al importar."""

from compilando import create_app

app = create_app()
