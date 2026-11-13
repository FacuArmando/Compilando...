# Compilando...

Plataforma universitaria de preguntas y respuestas con participación humana y respuestas de IA solicitadas mediante un botón.

## Estado actual

Base Flask modular, página inicial, registro de usuarios desde el navegador, `/health`, conexión SQLite y herramientas de calidad. El registro valida los datos, rechaza duplicados, guarda el hash de la contraseña y muestra una confirmación al volver al inicio. Los formularios están protegidos con Flask-WTF (CSRF). Login, preguntas, respuestas e IA siguen pendientes.

`registrar_usuario` en `compilando/modules/auth/services.py` valida los datos, guarda el correo en minúsculas, genera el hash y persiste la cuenta. Las contraseñas deben tener entre 8 y 128 caracteres. Los datos inválidos o repetidos producen un `ValueError` con un mensaje para mostrar en el formulario.

Para probar el registro, instalar las dependencias con `uv sync --locked`, aplicar `db upgrade`, iniciar el servidor y abrir `/auth/register` o pulsar «Crear una cuenta» desde el inicio. Los errores conservan usuario y correo, pero requieren volver a escribir la contraseña. El registro crea la cuenta; iniciar sesión será el siguiente paso.

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

Comprueba una consulta real y crea, si hace falta, `instance/compilando.sqlite`. SQLite se utiliza provisionalmente en desarrollo mientras el equipo confirma el motor. Para usar PostgreSQL habrá que configurar `DATABASE_URL` e incorporar su controlador.

La primera migración está en `migrations/versions/` y crea la tabla `usuarios`. Para aplicarla en cada copia local:

```bash
uv run flask --app compilando:create_app db upgrade
```

El paquete `auth` importa `Usuario` al cargarse, permitiendo que las migraciones descubran su tabla. Al cambiar o incorporar modelos, asegurarse de que se importen al cargar la aplicación y generar una nueva revisión:

```bash
uv run flask --app compilando:create_app db migrate -m "Describir el cambio de tablas"
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

Las pruebas comprueban el aislamiento entre aplicaciones, las migraciones, el servicio de registro y el recorrido del formulario: persistencia, hash, validaciones, duplicados, confirmación y rechazo de tokens CSRF ausentes, inválidos, vencidos o pertenecientes a otra sesión. Usan bases temporales y mantienen CSRF habilitado. Para cobertura: `uv run pytest --cov=compilando --cov-report=term-missing`.

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
