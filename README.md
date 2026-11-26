# Compilando...

Plataforma de preguntas y respuestas con participación humana y respuestas de IA solicitadas mediante un botón.

## Estado actual

Base Flask modular, página inicial, registro, inicio y cierre de sesión desde el navegador, `/health`, conexión SQLite y herramientas de calidad. El registro valida los datos, rechaza duplicados y guarda el hash de la contraseña. El login comprueba las credenciales y muestra el usuario conectado. Los formularios están protegidos con Flask-WTF (CSRF). La plataforma permite publicar y consultar preguntas y respuestas; permite solicitar respuestas reales de Gemini desde una pregunta, con sesión válida y confirmación del envío.

El inicio `/` es público: permite leer preguntas y respuestas, buscar y filtrar. El login `/auth/login` y el registro `/auth/register` son pantallas independientes, sin listado de preguntas debajo. Al intentar preguntar o responder, el visitante pasa por el login y luego vuelve al formulario correspondiente. Solo se admiten destinos internos conocidos para ese regreso. Publicar y modificar contenido requiere una sesión válida; «Mi cuenta» también es privada.

El listado muestra 20 preguntas por página, con navegación numerada antes del footer y conserva búsqueda y categoría al avanzar. Cuenta las respuestas sin cargarlas completas y mantiene un orden estable. Ver [paginación](docs/paginacion.md) para la migración de índices, las pruebas y el alcance de esta primera versión.

`registrar_usuario` en `compilando/modules/auth/services.py` valida los datos, guarda el correo en minúsculas, genera el hash y persiste la cuenta. Las contraseñas nuevas deben tener entre 8 y 18 caracteres. El login mantiene la compatibilidad con las contraseñas anteriores. Los datos inválidos o repetidos producen un `ValueError` con un mensaje para mostrar en el formulario.

Para probar el recorrido, instalar las dependencias con `uv sync --locked`, aplicar `db upgrade`, iniciar el servidor y crear una cuenta en `/auth/register`. Después ingresar en `/auth/login` con el correo y contraseña registrados. El inicio muestra el nombre de usuario y el botón «Cerrar sesión». Los errores conservan el correo, pero requieren volver a escribir la contraseña.

El login crea una sesión en la base; la cookie firmada contiene un identificador aleatorio y la base guarda su hash. La sesión vence a las 8 horas o tras 30 minutos de inactividad. Cerrar sesión requiere POST con CSRF e invalida también las copias anteriores de esa cookie. Hay límites de intentos compartidos en la base: por ventana de 15 minutos se admiten 5 envíos de login por correo, 30 por IP y 10 registros por IP; al superarlos se devuelve 429 con `Retry-After`. Los envíos válidos también cuentan.

Las rutas que requieren autenticación deben usar `@requiere_sesion` de `compilando.modules.auth.sessions`, debajo del decorador de ruta. Permite ejecutar la acción con el usuario validado en `g.usuario_actual`; si no hay sesión válida, redirige al login sin ejecutar la acción. Los POST conservan la protección CSRF. El módulo que implemente preguntas, respuestas o edición de datos debe aplicar esta protección y sus permisos específicos.

Las decisiones y controles están en [autenticación](docs/autenticacion.md). En producción se requiere HTTPS, un servidor WSGI, `APP_ENV=production`, una clave secreta aleatoria de al menos 32 caracteres y `TRUSTED_HOSTS` con los dominios permitidos. El servidor valida esa configuración y rechaza HTTP. El comando local de desarrollo se mantiene limitado a `127.0.0.1`.

La pantalla «Mi cuenta», disponible en `/auth/account` desde el menú del usuario o la barra lateral, permite consultar el nombre de usuario y el correo de la cuenta conectada. Requiere una sesión válida. Incluye el cambio de contraseña (#27): pide la actual, una nueva de 8 a 18 caracteres y su confirmación. Guarda el nuevo hash e invalida todas las sesiones de esa cuenta en una sola transacción; luego pide ingresar con la nueva contraseña.

También permite cambiar el correo (#28), confirmando la contraseña actual. Valida su formato, lo guarda en minúsculas y rechaza correos usados por otra cuenta. El cambio conserva el usuario y sus publicaciones, invalida sus sesiones y pide ingresar con el correo nuevo y la misma contraseña. Ambos cambios de credenciales comparten el límite de intentos de verificación de contraseña. El nombre de usuario sigue siendo de consulta.

Las preguntas admiten archivos de código opcionales (#20), tanto desde el formulario desplegable del inicio como desde `/questions/publish`. Se pueden seleccionar o arrastrar, revisar en tarjetas y quitar antes de publicar. La pregunta muestra los adjuntos con opciones para ver el texto y descargar el original. Inicialmente se admiten `.java`, `.py`, `.js`, `.jsx` y `.txt`, hasta 10 archivos, 1 MB por archivo y 5 MB en total. Se requiere texto UTF-8; nunca se ejecuta ni compila el contenido. Los adjuntos son públicos, igual que la pregunta. Ver [adjuntos](docs/adjuntos.md) para almacenamiento, límites y migración.

La validación de archivos (#21) revisa la selección en el navegador antes de enviarla y repite los controles en el servidor. Informa los límites exactos, rechaza archivos vacíos o binarios, contenido que no sea UTF-8 y nombres inválidos. Si una selección falla, conserva los adjuntos válidos que ya estaban elegidos; si el servidor rechaza una carga, no publica parcialmente la pregunta. La descarga conserva los archivos originales, incluso con acentos o saltos de línea de Windows. No se exige que el código compile.

Las consultas de IA se guardan identificadas con proveedor y modelo, sin borrar el borrador de una respuesta humana. Los adjuntos se incluyen solo si se selecciona esa opción y el contexto completo no supera 48 KB. La primera versión comparte una respuesta de IA por pregunta y evita llamadas duplicadas. Para configurarla, aplicar la nueva migración y conocer los límites, ver [integración con Gemini](docs/ia.md).

## Preparación

Requisitos: Python 3.12, uv, Git, editor y navegador. Ver [lista completa](docs/herramientas.md).

Desde la raíz del repositorio:

```bash
uv sync --locked
cp .env.example .env
uv run python -c 'import secrets; print(secrets.token_hex(32))'
```

Pegar la clave generada en `SECRET_KEY` dentro de `.env`. Cada integrante usa su propia clave. En la copia preparada por Codex, `.env` ya se generó y no hace falta reemplazarlo para arrancar. La aplicación requiere una clave de al menos 32 caracteres; no compartir ni incluir `.env` en Git.

`uv sync` instala el proyecto y las herramientas de desarrollo en `.venv`. `uv run` usa ese entorno sin activarlo a mano. Se incluyen `pyproject.toml`, `.python-version` y `uv.lock` en Git para compartir configuración y versiones.

## Modo administrador

El modo administrador permite gestionar y moderar aspectos de la comunidad **Compilando...**, brindando acceso a funcionalidades exclusivas que no están disponibles para los usuarios comunes.

Entre sus funcionalidades se encuentran:

- **Gestión de categorías:** crear nuevas categorías y editar las existentes.
- **Gestión de etiquetas:** crear, editar y eliminar etiquetas.
- **Administración de la comunidad:** acceder al panel de administración y a sus herramientas de gestión.

### Activación

Para habilitar el modo administrador, es necesario configurar un código de activación local.

#### 1. Generar el código

Desde la terminal, ejecutá el siguiente comando en la raíz del proyecto:

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copiá el código generado.

#### 2. Configurar el archivo `.env`

Agregá el código generado a la siguiente variable de entorno:

```env
ADMIN_ACTIVATION_CODE=tu_codigo_generado
```

Si la variable ya existe, reemplazá su valor.

#### 3. Activar el modo administrador

Iniciá la aplicación, ingresá a tu cuenta y dirígete al apartado "Mi cuenta", al final, utilizá el código de activación configurado para habilitar los permisos de administrador.

**Importante:** cada desarrollador debe generar su propio código de activación. El archivo `.env` contiene información privada y no debe subirse al repositorio ni compartirse con otras personas.

El modo administrador cuenta con una implementación básica, pensada para cubrir las necesidades iniciales de gestión de la comunidad. Por el momento, sus funcionalidades se limitan a la administración de categorías y etiquetas, y podrán ampliarse a medida que evolucione el proyecto.

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

En SQLite, el buscador ignora acentos y mayúsculas en títulos, cuerpos y etiquetas, conservando `ñ` y símbolos como `C++`. La aplicación registra el normalizador en cada conexión, sin modificar el contenido guardado ni requerir migraciones. Al incorporar otro motor habrá que adaptar esa normalización; por ahora los demás motores conservan la búsqueda con `ILIKE`.

Las búsquedas exigen los conceptos indicados y ordenan por coincidencias en título, etiquetas y cuerpo, con respuestas aceptadas como desempate. Se omiten algunos artículos y preposiciones (`de`, `del`, `el`, `la`, `los`, `las`, `en`) y se reconoce la equivalencia entre `POO` y «programación orientada a objetos». Si no hay resultados, puede aparecer una sugerencia explícita para un error de escritura: usa vocabulario de etiquetas/categorías, evita opciones ambiguas y comprueba que la consulta sugerida tenga resultados dentro de la categoría elegida. El texto escrito nunca se reemplaza automáticamente.

Las migraciones están en `migrations/versions/`: crean `usuarios`, `sesiones` y `limites_autenticacion`. Para aplicarlas en cada copia local, también después de actualizar el proyecto:

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

Las pruebas comprueban registro, login, logout, persistencia, hash, validaciones, migraciones y aislamiento de bases. Incluyen CSRF ausente, inválido, vencido o ajeno; cookies manipuladas, rotación, revocación y vencimiento de sesiones; intentos concurrentes y configuración de producción. Usan bases temporales y mantienen CSRF habilitado. Para cobertura: `uv run pytest --cov=compilando --cov-report=term-missing`.

El archivo `.github/workflows/checks.yml` configura estas comprobaciones para GitHub Actions al subir cambios. Todavía no se ejecutó en GitHub.

## Documentación

- [Herramientas y requisitos](docs/herramientas.md).
- [Árbol y responsabilidades](docs/arquitectura.md).
- [Alcance inicial](docs/alcance-inicial.md).
- `Documentación/`: UML y justificación originales del equipo.

Siguiente hito: publicar pregunta → consultar pregunta, con autor autenticado, persistencia y pruebas de permisos.

## Easter Egg

👀 Hay un pequeño secreto escondido en Compilando.

Quizás el logo del **pie de página** tenga algo más para ofrecer de lo que aparenta. ¿Y si **cinco pequeños toques seguidos** fueran suficientes para revelar algo inesperado? 🤫

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
