"""Páginas de error compartidas por todas las rutas de la aplicación."""

from flask import render_template


def not_found(_error):
    """Mostrar una salida útil sin convertir una página inexistente en un éxito."""
    return render_template("errors/404.html"), 404
