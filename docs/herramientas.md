# Herramientas y requisitos

Comprobación local: 5 de noviembre de 2026. Las versiones indicadas son las instaladas; las versiones exactas de todas las dependencias se conservan en `uv.lock`.

## Entorno de cada integrante

| Requisito | Uso | Estado en este equipo |
| --- | --- | --- |
| Python 3.12 | Ejecutar el proyecto con una versión compartida | Instalado: 3.12.14 |
| uv | Entorno, dependencias y ejecución | Instalado: 0.12.5 |
| Git | Ramas e historial | Instalado: 2.49.0 |
| GitHub | Colaboración y revisión | Repositorio descargado; permisos de escritura de cada integrante por comprobar |
| Editor, por ejemplo VS Code | Editar y navegar el código | Usar el habitual del equipo |
| Terminal | Ejecutar comandos | Disponible |
| Navegador | Usar la aplicación | Disponible para la comprobación |
| Internet | Descargar dependencias, colaborar e invocar IA remota | Necesario en esas operaciones |

El `python3` del sistema apunta a 3.9.6. Se utiliza `uv run` para trabajar con Python 3.12 sin modificar el Python del sistema. Si a otro integrante le falta 3.12, puede instalarlo con `uv python install 3.12` una vez instalado uv.

## Dependencias incluidas ahora

Se instalan juntas con `uv sync --locked`, dentro del entorno del proyecto.

| Dependencia | Función |
| --- | --- |
| Flask | Servidor web, rutas, Blueprints y fábrica |
| Flask-SQLAlchemy / SQLAlchemy | ORM y conexión a datos |
| Flask-Migrate / Alembic | Migraciones del esquema de datos |
| python-dotenv | Lectura de `.env` desde el comando Flask |
| pytest | Pruebas automatizadas |
| pytest-cov | Informes de cobertura |
| Ruff | Revisión de código y formato |
| Hatchling | Construcción e instalación del paquete local |

SQLAlchemy y Alembic se instalan como dependencias de sus integraciones. Flask incluye Jinja para HTML y Werkzeug para utilidades HTTP, entre otras bibliotecas. SQLite se usa mediante Python y no necesita una instalación separada.

## Para etapas posteriores

| Etapa | Requisito o decisión |
| --- | --- |
| Autenticación | Acordar sesión o JWT según consigna; agregar la integración y definir vencimiento y cierre de sesión |
| Formularios | Validación y protección CSRF al incorporar acciones que modifican datos |
| Contratos | Pydantic aparece en el taller; incorporarlo al definir entradas y salidas |
| IA | Elegir proveedor/modelo, añadir su cliente y una credencial de desarrollo |
| PostgreSQL | Si se adopta: base accesible y controlador de Python |
| Despliegue | Docker y plataforma según consigna; cuenta de Vercel si se elige ese destino |
| Automatización | GitHub Actions ya tiene una configuración local, pendiente de subir y ejecutar |

PyTorch y Scikit-Learn pertenecen a los ejemplos predictivos del curso. Su necesidad depende de si se debe ejecutar o entrenar un modelo local; llamar a una API de LLM no implica por sí mismo necesitarlos.

## Opcionales

- Extensiones Python y Ruff para el editor.
- Cliente de API, o herramientas del navegador y `curl`.
- Visor de SQLite para inspeccionar datos.
- Astah para editar el `.asta` del UML.

La primera interfaz utiliza HTML/Jinja y CSS dentro de Flask. Node.js, npm y un framework de frontend no forman parte del entorno inicial.

Fuentes: [uv](https://docs.astral.sh/uv/guides/projects/), [Flask](https://flask.palletsprojects.com/en/stable/installation/), [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/en/stable/quickstart/), [Flask-Migrate](https://flask-migrate.readthedocs.io/en/latest/), [uv en GitHub Actions](https://docs.astral.sh/uv/guides/integration/github/).
