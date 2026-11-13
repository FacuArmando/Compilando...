"""Autenticación y cuentas de usuario.

Importa el modelo para que SQLAlchemy y las migraciones descubran su tabla
cuando la aplicación carga este módulo.
"""

from compilando.modules.auth.models import Usuario

__all__ = ["Usuario"]
