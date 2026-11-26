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
    @app.cli.command("check-db")
    def check_db() -> None:
        """Comprobar la conexión sin crear tablas del dominio."""
        db.session.execute(text("SELECT 1"))
        click.echo("Conexión con la base de datos: OK")

    @app.cli.command("check-postgres")
    def check_postgres() -> None:
        """Comprobar PostgreSQL sin aceptar por error el fallback local de SQLite."""
        if db.engine.dialect.name != "postgresql":
            raise click.ClickException(
                "No hay una conexión PostgreSQL configurada. Completá el perfil privado."
            )
        try:
            db.session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            db.session.rollback()
            raise click.ClickException(
                "No se pudo conectar a PostgreSQL. Revisá host, contraseña, TLS y modo de pool. "
                "No compartas la URL completa ni las credenciales."
            ) from None
        finally:
            db.session.remove()
        click.echo("Conexión PostgreSQL: OK. No se crearon tablas ni se copiaron datos.")
