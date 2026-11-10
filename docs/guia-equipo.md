# Compilando... — qué construimos y cómo revisarlo entre los tres

Fecha: 5 de noviembre de 2026. Esta guía describe la base local existente, sus motivos y sus límites. No cambia los requisitos de la materia.

## 1. Qué existe hoy

Tenemos una copia local del repositorio original con una aplicación Flask que arranca mediante uv. Se puede abrir una página inicial y consultar el estado del proceso web.

También están preparados el acceso a SQLite, la infraestructura de migraciones, una prueba de aislamiento entre aplicaciones y las herramientas de formato y revisión de código.

Estado confirmado al preparar esta guía:

| Elemento | Estado |
| --- | --- |
| Servidor local | Responde en `http://127.0.0.1:5051` |
| Inicio | Se renderiza una plantilla HTML con su CSS |
| `/health` | Devuelve `{"application":"compilando","status":"ok"}` |
| SQLite | La consulta de conexión funciona |
| Tablas de negocio | Ninguna: todavía no hay usuarios, preguntas ni respuestas |
| pytest | Una prueba, aprobada |
| Ruff | Revisión y formato aprobados |
| GitHub Actions | Archivo preparado; ejecución remota pendiente |
| Login, preguntas, respuestas e IA | Pendientes de implementar |

La página inicial comunica que el producto está en construcción. Las carpetas de funcionalidades futuras contienen únicamente sus paquetes y descripciones.

## 2. Qué se hizo con Git

1. Se descargó una copia del repositorio público, conservando la documentación original.
2. Se creó la rama local `chore/base-flask-uv`.
3. Se agregaron archivos y se amplió el README dentro de esa copia.

**No se hicieron commits ni se ejecutó una subida a GitHub.** La base se trasladó a la carpeta habitual de la universidad, conservando su propio historial: el último commit local sigue siendo `e449d3f`. Los cambios nuevos siguen sin incorporarse al historial.

Para revisar esto, desde la raíz de la copia:

```bash
git branch --show-current
git status --short
git log -1 --oneline
```

Resultados actuales esperados:

- La rama es `chore/base-flask-uv`.
- `M README.md` significa que un archivo que Git ya conocía fue modificado.
- `?? compilando/`, `?? docs/`, etc. indican archivos nuevos aún no incorporados al historial.
- El último commit empieza por `e449d3f`.

Esto permite revisar el estado local. La explicación sobre las acciones realizadas se refiere al trabajo de esta conversación.

## 3. Para qué sirve cada herramienta

**Python** ejecuta el código. Elegimos la serie 3.12, compatible con la orientación del taller. La instalación encontrada es 3.12.14.

**uv** gestiona el entorno y las dependencias y ejecuta comandos dentro de ese entorno. `.venv/` contiene las bibliotecas locales del proyecto. `uv run` evita tener que activar manualmente ese entorno antes de cada comando.

**Flask** es el framework web: relaciona direcciones con funciones de Python y construye respuestas HTTP. Su servidor de desarrollo atiende las solicitudes mientras el proceso está encendido.

**Jinja** transforma plantillas HTML en páginas. **CSS** define su presentación. Ambos se usan dentro de esta primera aplicación, sin una aplicación de frontend separada.

**SQLAlchemy y Flask-SQLAlchemy** permiten conectar la aplicación a una base y, cuando incorporemos modelos, guardar y consultar entidades. **SQLite** es el motor local; su base es un archivo en `instance/`.

**Alembic y Flask-Migrate** preparan el historial de cambios del esquema: por ejemplo, crear la tabla de usuarios o agregar una columna. Hoy solo existe su infraestructura; no se generaron revisiones ni tablas de negocio.

**pytest** ejecuta pruebas. **pytest-cov** puede calcular cobertura. **Ruff** encuentra determinados errores y comprueba el formato. El formato consistente facilita revisar cambios de tres personas.

**python-dotenv** permite que el comando Flask lea variables del archivo `.env`. **Hatchling** permite instalar y construir el paquete Python del proyecto.

La lista completa y las herramientas que se agregarán más adelante están en [herramientas.md](herramientas.md).

## 4. Qué sucede al arrancar

El comando de desarrollo es:

```bash
uv run flask --app compilando:create_app run --host 127.0.0.1 --port 5051
```

Se interpreta así:

1. `uv run`: ejecutar dentro del entorno del proyecto.
2. `flask`: utilizar la herramienta de Flask.
3. `--app compilando:create_app`: buscar el paquete `compilando` y llamar a su función `create_app`.
4. `run`: iniciar el servidor de desarrollo.
5. `--host 127.0.0.1`: atender en esta computadora.
6. `--port 5051`: utilizar el puerto 5051.

Por eso esta dirección sirve para trabajar localmente. Otro integrante no puede abrir la aplicación de esta computadora escribiendo `127.0.0.1` en la suya: esa dirección apunta a su propia máquina.

Cuando se abre `/` en el navegador, Flask ejecuta `index()` en `compilando/modules/system/routes.py`. Esa función renderiza `templates/system/index.html`, que extiende `templates/base.html`. El navegador solicita el CSS de `static/css/app.css` para aplicar el estilo.

## 5. Por qué existe create_app

`create_app` es una función que arma y devuelve una aplicación Flask. En esta base:

1. Crea la aplicación.
2. Carga la configuración.
3. Permite reemplazar configuración para pruebas.
4. Prepara el directorio local de datos.
5. Vincula SQLAlchemy y la herramienta de migraciones.
6. Registra el módulo de inicio y estado.
7. Registra el comando `check-db`.

Esto permite crear una aplicación para desarrollo y otra para pruebas con configuraciones independientes. Es el patrón Application Factory presentado por Flask y por el material del curso.

La prueba actual verifica una consecuencia concreta: crear una tabla de prueba en una base en memoria no debe hacerla aparecer en la base de una segunda instancia de la aplicación.

## 6. Qué significa modularizar en este proyecto

La carpeta exterior es el repositorio; la interior `compilando/` es el paquete Python de la aplicación.

```text
repositorio/
├── compilando/
│   ├── __init__.py        # Armado de la aplicación
│   ├── config.py          # Configuración
│   ├── extensions.py      # Herramientas compartidas
│   ├── commands.py        # Comandos de mantenimiento
│   ├── modules/
│   │   ├── system/        # Implementado: inicio y estado
│   │   ├── auth/          # Pendiente: cuentas y login
│   │   ├── questions/     # Pendiente: publicar y consultar preguntas
│   │   ├── answers/       # Pendiente: responder y representar autoría
│   │   └── ai/            # Pendiente: solicitar y generar respuesta de IA
│   ├── templates/         # Pantallas HTML
│   └── static/            # CSS y recursos
├── tests/
├── migrations/
├── docs/
├── Documentación/         # UML original
├── pyproject.toml
├── uv.lock
└── README.md
```

El Blueprint que funciona hoy es `system`. Un Blueprint agrupa rutas para registrarlas en la aplicación. Los módulos futuros todavía no tienen Blueprints ni rutas registradas.

Al desarrollar una función, agregaremos las separaciones que requiera. Ejemplo propuesto para preguntas:

- `routes.py`: recibir una solicitud y devolver una respuesta HTTP.
- `services.py`: coordinar el caso de uso, sus reglas y permisos.
- `models.py`: representar preguntas y relaciones persistentes.
- `repositories.py`: consultas a datos que necesiten los servicios.
- `schemas.py`: validar entradas y salidas cuando corresponda.

La estructura por funcionalidades mantiene cerca los archivos que cambian por la misma necesidad. Las responsabilidades dentro de cada módulo facilitan las pruebas y la revisión. Tener carpetas es solo el comienzo: mantener esos límites en el código será parte del trabajo.

## 7. Qué archivos ayudan a compartir el entorno

| Archivo | Significado |
| --- | --- |
| `pyproject.toml` | Nombre del proyecto, dependencias y configuración de herramientas |
| `uv.lock` | Versiones resueltas de las dependencias para reproducir la instalación |
| `.python-version` | Serie de Python utilizada: 3.12 |
| `.env.example` | Nombres de variables de configuración, sin credenciales reales |
| `.env` | Valores locales de esta computadora; ignorado por Git |
| `.gitignore` | Archivos locales que no se deben incorporar al repositorio |
| `README.md` | Instrucciones y estado de la implementación |

Cada integrante crea su `.venv`, su `.env` y su archivo SQLite. Se comparte el código y el archivo de dependencias; cada entorno conserva sus datos locales.

La estructura usa el paquete en la raíz. Durante el arranque se detectó que macOS volvía a marcar como oculto un archivo `.pth` del entorno editable y Python lo omitía. La disposición elegida evita depender de ese archivo para ejecutar el proyecto desde su raíz. Se documenta aquí como una particularidad encontrada en este equipo.

## 8. Cómo corroborarlo personalmente

Primero, abrir una terminal en la carpeta que contiene `pyproject.toml`. En esta computadora es:

```bash
cd "/Users/mati/Documents/UNRC/ingenieria de software/taller_1/Compilando..."
```

### A. Confirmar que Flask conoce las rutas

```bash
uv run flask --app compilando:create_app routes
```

Hoy deben aparecer `/`, `/health` y `/static/<path:filename>`. No aparecen rutas de login ni de publicación, porque todavía no existen.

### B. Abrir la aplicación

Con el servidor encendido, abrir `http://127.0.0.1:5051` y `http://127.0.0.1:5051/health`.

El inicio muestra el proyecto en construcción. El segundo enlace devuelve el estado del proceso. Para observar también el estado HTTP desde una terminal:

```bash
curl -i http://127.0.0.1:5051/health
```

Se espera HTTP 200 y un JSON con `application: compilando` y `status: ok`. Esta comprobación no evalúa la base ni proveedores de IA.

### C. Comprobar SQLite

```bash
uv run flask --app compilando:create_app check-db
```

Resultado esperado: `Conexión con la base de datos: OK`. Ejecuta `SELECT 1`; verifica conectividad, pero no implica que ya existan usuarios ni que se haya implementado su persistencia.

### D. Ejecutar prueba y revisión

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Hoy se espera una prueba aprobada, revisión sin errores y archivos ya formateados. Esa única prueba verifica aislamiento de bases en memoria. Las pruebas de permisos, login, publicación, respuestas e IA se incorporarán con las funciones correspondientes.

### E. Revisar el código que produce el resultado

Leer, en este orden: `compilando/__init__.py`, `compilando/modules/system/routes.py`, `compilando/templates/system/index.html`, `compilando/config.py` y `tests/test_factory.py`.

Relacionar la página que se ve con la función que la genera y con la plantilla que renderiza es una buena primera revisión del código.

## 9. ¿Es lo que debemos hacer?

Es un punto de partida razonable y coherente con Python, uv, Flask, modularidad, persistencia y pruebas del taller. Permite comenzar el producto con un entorno ejecutable y comprobable.

Algunas piezas se prepararon para los pasos siguientes: SQLAlchemy, migraciones y la configuración de GitHub Actions. La página inicial por sí sola no necesita todas esas piezas.

Esta base no decide toda la arquitectura. Falta acordar autenticación con sesión/JWT, permisos del botón de IA, proveedor, validaciones definitivas y entregables específicos de la consigna. SQLite y Jinja son elecciones iniciales revisables. El UML se debe actualizar cuando cambien decisiones, incluyendo el pedido de IA por botón.

Para la defensa académica conviene que cada integrante pueda explicar un caso de uso, las responsabilidades de sus componentes, su persistencia y cómo se prueba.

## 10. Cómo trabajar siendo tres

Primero recorrer juntos el arranque y acordar los contratos compartidos: qué representa un usuario, cómo se obtiene su identidad autenticada y qué datos requiere una pregunta.

Una distribución posible para el primer hito:

| Responsable | Tarea inicial | Revisión |
| --- | --- | --- |
| Integrante A | Usuarios y login, con sus pruebas | B revisa |
| Integrante B | Preguntas: publicar, listar y consultar, con sus pruebas | C revisa |
| Integrante C | Pantallas del recorrido y comprobación de integración, con sus pruebas | A revisa |

Los roles pueden rotar en el siguiente hito. Los cambios de esquema se coordinan para evitar migraciones incompatibles. Cada integrante prueba su trabajo y otro lo revisa.

El hito se demuestra con dos usuarios: uno inicia sesión y publica una pregunta; el otro puede verla. La pregunta sigue existiendo tras reiniciar la aplicación. Luego se incorporan la respuesta humana y el botón de IA.

Para probar esta base desde otra computadora, primero hay que recibir los mismos archivos de código: todavía no están en GitHub. Una copia compartida debe excluir `.env`, `.venv`, bases locales y cachés. Cada integrante sigue el README para crear su entorno. El modo y momento de compartir/versionar los cambios quedan bajo decisión del equipo; en esta conversación se mantiene la instrucción de no subirlos.

## Referencias

- [Material de la materia](https://se-course-with-flask-project.vercel.app/).
- [Application Factories de Flask](https://flask.palletsprojects.com/en/stable/patterns/appfactories/).
- [Blueprints de Flask](https://flask.palletsprojects.com/en/stable/blueprints/).
- [Proyectos con uv](https://docs.astral.sh/uv/guides/projects/).
