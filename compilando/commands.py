"""Registra comandos propios del proyecto para ejecutar desde la terminal.

Incluye check-db, que hace una consulta sencilla para comprobar
que la aplicación puede conectarse a la base de datos.
"""

import click
from flask import Flask
from sqlalchemy import text

from compilando.extensions import db


def register_commands(app: Flask) -> None:
    @app.cli.command("check-db")
    def check_db() -> None:
        """Comprobar la conexión sin crear tablas del dominio."""
        db.session.execute(text("SELECT 1"))
        click.echo("Conexión con la base de datos: OK")
