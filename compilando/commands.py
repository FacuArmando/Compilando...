"""Registra comandos propios del proyecto para ejecutar desde la terminal.

Incluye check-db, que hace una consulta sencilla para comprobar
que la aplicación puede conectarse a la base de datos.
"""

import click
from flask import Flask
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from compilando.extensions import db


def register_commands(app: Flask) -> None:
    @app.cli.command("database-info")
    def database_info() -> None:
        """Mostrar el motor seleccionado sin abrir conexión ni revelar credenciales."""
        if db.engine.dialect.name == "sqlite":
            click.echo("Base activa: SQLite local")
        else:
            click.echo("Base activa: PostgreSQL / Supabase")
            click.echo(f"Modo de conexión: {app.config['DATABASE_POOL_MODE']}")
        click.echo("Cambiar de base no copia ni sincroniza datos.")

    @app.cli.command("check-db")
    def check_db() -> None:
        """Comprobar la conexión sin crear tablas del dominio."""
        try:
            db.session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            raise click.ClickException(
                "No se pudo conectar a la base seleccionada. Revisá el perfil y la red; "
                "no compartas credenciales."
            ) from None
        finally:
            db.session.remove()
        click.echo("Conexión con la base de datos: OK")
