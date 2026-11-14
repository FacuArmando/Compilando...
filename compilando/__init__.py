"""Crea la aplicación Flask y conecta sus componentes mediante create_app.

Carga la configuración, inicializa las herramientas de base de datos
y registra las rutas de las páginas y los comandos de terminal.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from flask import Flask

from compilando.commands import register_commands
from compilando.config import load_config
from compilando.extensions import csrf, db, migrate
from compilando.modules.auth.routes import bp as auth_bp
from compilando.modules.auth.security import init_app as init_security
from compilando.modules.auth.sessions import init_app as init_auth
from compilando.modules.system.routes import bp as system_bp

from compilando.modules.questions.routes import bp as questions_bp

import compilando.modules.questions
import compilando.modules.categories
import compilando.modules.questions
import compilando.modules.tags

def create_app(test_config: Mapping[str, Any] | None = None) -> Flask:
    """Crear una instancia independiente para desarrollo, pruebas o despliegue."""
    project_root = Path(__file__).resolve().parents[1]
    app = Flask(__name__, instance_path=str(project_root / "instance"))
    app.config.from_mapping(load_config())
    if test_config is not None:
        app.config.from_mapping(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    migrate.init_app(app, db, directory=str(project_root / "migrations"))
    init_security(app)
    init_auth(app)
    csrf.init_app(app)
    app.register_blueprint(system_bp)
    app.register_blueprint(auth_bp)
    register_commands(app)
    app.register_blueprint(questions_bp)
    return app
