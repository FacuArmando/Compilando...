# Compilando...

Plataforma universitaria de preguntas y respuestas con participación humana y respuestas de IA solicitadas mediante un botón.

## Estado actual

Base Flask modular, página inicial, `/health`, conexión SQLite, infraestructura de migraciones y herramientas de calidad. Los paquetes de autenticación, preguntas, respuestas e IA están reservados; sus funciones y tablas todavía no se implementaron.

## Preparación

Requisitos: Python 3.12, uv, Git, editor y navegador. Ver [lista completa](docs/herramientas.md).

Desde la raíz del repositorio:

```bash
uv sync --locked
cp .env.example .env
uv run python -c 'import secrets; print(secrets.token_hex(32))'
```

Pegar la clave generada en `SECRET_KEY` dentro de `.env`. Cada integrante usa su propia clave. En la copia preparada por Codex, `.env` ya se generó y no hace falta reemplazarlo para arrancar.

`uv sync` instala el proyecto y las herramientas de desarrollo en `.venv`. `uv run` usa ese entorno sin activarlo a mano. Se incluyen `pyproject.toml`, `.python-version` y `uv.lock` en Git para compartir configuración y versiones.

## Servidor local

```bash
uv run flask --app compilando:create_app run --host 127.0.0.1 --port 5051
```

Abrir <http://127.0.0.1:5051>. El estado del proceso está en <http://127.0.0.1:5051/health>; no comprueba base de datos ni proveedores externos. Detener con `Ctrl+C`. Para recargar cambios automáticamente durante el desarrollo, añadir `--debug` después de `run`. El despliegue usará otra configuración de servidor.

## Base de datos

```bash
uv run flask --app compilando:create_app check-db
```

Comprueba una consulta real y crea, si hace falta, `instance/compilando.sqlite`. SQLite no requiere un servicio adicional. Todavía no hay tablas de negocio. Para usar PostgreSQL habrá que configurar `DATABASE_URL` e incorporar su controlador.

La infraestructura de Alembic está en `migrations/`. Al incorporar modelos, importarlos desde la fábrica para que sean descubiertos y ejecutar:

```bash
uv run flask --app compilando:create_app db migrate -m "Crear usuarios"
# Revisar el archivo generado antes de aplicarlo y guardarlo en Git.
uv run flask --app compilando:create_app db upgrade
```

En una copia nueva con revisiones existentes, aplicar `db upgrade`. No repetir `db init` ni regenerar migraciones compartidas.

## Comprobaciones

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

La prueba inicial comprueba que dos aplicaciones creadas por la fábrica no comparten su base en memoria. Las pruebas del producto se incorporarán con cada función. Para cobertura: `uv run pytest --cov=compilando --cov-report=term-missing`.

El archivo `.github/workflows/checks.yml` configura estas comprobaciones para GitHub Actions al subir cambios. Todavía no se ejecutó en GitHub.

## Documentación

- [Herramientas y requisitos](docs/herramientas.md).
- [Árbol y responsabilidades](docs/arquitectura.md).
- [Alcance inicial](docs/alcance-inicial.md).
- `Documentación/`: UML y justificación originales del equipo.

Siguiente hito: login → publicar pregunta → consultar pregunta, con persistencia y pruebas.

# Integrantes Del Grupo:

    #Integrante 1:
      - Nombre: Facundo
      - Apellido: Armando
      
    #Integrante 2:
      - Nombre: Matias
      - Apellido: Ponce
    
    #Integrante 3:
      - Nombre: Milagros
      - Apellido: Carmona
