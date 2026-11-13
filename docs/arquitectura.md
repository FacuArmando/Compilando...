# Primera propuesta de estructura

Aplicación Flask organizada por funcionalidad, ejecutada como una unidad y con una base de datos. La fábrica `create_app` configura cada instancia y conecta sus extensiones.

## Árbol existente

```text
compilando/
├── Documentación/              # UML y justificación originales
├── docs/                       # Herramientas, arquitectura y alcance
├── compilando/
│   ├── __init__.py             # create_app
│   ├── config.py               # Configuración por entorno
│   ├── extensions.py           # SQLAlchemy y Flask-Migrate
│   ├── commands.py             # check-db
│   ├── modules/
│   │   ├── system/routes.py    # Inicio y /health: implementados
│   │   ├── auth/               # Registro, login, logout y sesiones persistentes
│   │   ├── questions/          # Preguntas: reservado
│   │   ├── answers/            # Respuestas y autoría: reservado
│   │   └── ai/                 # Solicitudes y proveedores: reservado
│   ├── templates/              # HTML: base y pantallas por módulo
│   └── static/css/             # Estilos
├── migrations/                 # Alembic: usuarios, sesiones y límites de intentos
├── tests/                      # Aislamiento, migraciones, registro y autenticación
├── instance/                   # SQLite local; ignorado por Git
├── .github/workflows/checks.yml
├── .env.example
├── .python-version
├── .gitignore
├── pyproject.toml
├── uv.lock
└── README.md
```

Los módulos reservados contienen únicamente su paquete con una descripción. No tienen funcionalidades simuladas.

## Crecimiento de cada módulo

Al desarrollar preguntas se incorporarán los archivos necesarios para sus casos de uso:

```text
modules/questions/
├── __init__.py
├── routes.py          # Blueprint, solicitudes y resultados HTTP
├── services.py        # Casos de uso, reglas y permisos
├── models.py          # Entidades persistentes y relaciones
├── repositories.py    # Consultas y acceso a datos que requieran los servicios
└── schemas.py         # Validación de entradas y salidas, cuando corresponda
```

Las rutas delegan en servicios; los servicios coordinan reglas y acceso a datos. Los repositorios no deciden permisos. Se crean estas separaciones al implementar casos reales, sin una jerarquía genérica de repositorios vacíos.

Las plantillas se ubicarán en `templates/questions/`, `templates/auth/`, etc. Los Blueprints se registran en la fábrica al tener rutas. Los modelos deben importarse allí al incorporarlos para que Alembic los descubra.

## Decisiones iniciales

- Python 3.12 y uv, coherentes con el taller y con dependencias versionadas.
- Application Factory y Blueprints para módulos y configuraciones independientes.
- SQLite en local para arrancar sin un servicio de base adicional. PostgreSQL requerirá configurar y probar su conexión y comportamiento.
- Jinja, HTML y CSS para la primera interfaz dentro de Flask.
- Strategy para IA al implementar el botón: distinguir al solicitante humano del autor IA y tratar los fallos del proveedor.

La autenticación usa sesiones persistidas en la base, siguiendo `Sesion` del UML.
La decisión, los controles y la configuración de producción están documentados en
[autenticacion.md](autenticacion.md). El proveedor de IA sigue pendiente.

Se utiliza un paquete en la raíz, una disposición habitual para una aplicación Flask pequeña. Esto también permite arrancar desde el repositorio sin depender de un archivo `.pth` de instalación editable: en este equipo macOS vuelve a marcar esos archivos como ocultos y Python los omite. La estructura sigue siendo modular y el proyecto también puede construirse como paquete.

## Alcance real de esta entrega

- `/`: página inicial con enlaces de ingreso o nombre del usuario y cierre de sesión.
- `/health`: disponibilidad del proceso web, sin consultar servicios externos.
- `check-db`: consulta real a SQLite.
- Registro, login y logout con CSRF, sesiones revocables en la base y límites de intentos.
- Migraciones para usuarios, sesiones y contadores de autenticación.
- Preguntas, respuestas y llamadas a IA pendientes del siguiente hito.

Fuentes: [Application Factories](https://flask.palletsprojects.com/en/stable/patterns/appfactories/), [Blueprints](https://flask.palletsprojects.com/en/stable/blueprints/).
