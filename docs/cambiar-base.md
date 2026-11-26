# Elegir SQLite o Supabase

Cada integrante elige la base en su `.env` personal y arranca Flask manualmente. Cambiar la selección no copia datos, no migra tablas ni borra bases.

## Uso cotidiano

Detener el servidor anterior con `Ctrl+C` y elegir un valor en el `.env` personal:

```dotenv
# Base local de este integrante; no necesita credenciales de Supabase.
DATABASE_BACKEND=sqlite

# Base remota configurada en su perfil privado.
# DATABASE_BACKEND=supabase
```

Iniciar desde la raíz del proyecto:

```bash
uv run flask --app compilando:create_app run --port 5051
```

Abrir `http://127.0.0.1:5051`. Detener con `Ctrl+C` en esa misma terminal. Para recargar cambios de código, agregar `--reload` al comando. Un cambio de base requiere reiniciar el servidor, no solo recargar la página. No usar este servidor de desarrollo para producción.

Cada base conserva sus propias cuentas, sesiones, preguntas y respuestas. Es normal volver a iniciar sesión al cambiar. Para evitar conflictos de cookies y confusión sobre los datos, usar un solo modo a la vez en el mismo navegador/host. No es un interruptor dentro de la web que cambie la base para todos los usuarios.

## Primera preparación de SQLite

1. Instalar dependencias con `uv sync --locked`.
2. Tener un `.env` propio con `SECRET_KEY` válida, según la preparación del README.
3. Elegir `DATABASE_BACKEND=sqlite` en ese `.env` y ejecutar una vez las migraciones de la copia local:

```bash
uv run flask --app compilando:create_app database-info
# Confirmar que indique SQLite local antes de ejecutar el siguiente comando.
uv run flask --app compilando:create_app db upgrade
uv run flask --app compilando:create_app run --port 5051
```

El archivo normal es `instance/compilando.sqlite`. Opcionalmente `SQLITE_DATABASE_URL` permite elegir otro archivo SQLite. El selector SQLite ignora `DATABASE_URL` remoto y no lee las credenciales de Supabase.

## Primera preparación de Supabase

Crear/llenar **una sola vez** `.env.supabase.local` en la raíz, con la conexión del proyecto al que se tiene acceso:

```dotenv
DATABASE_URL='postgresql+psycopg://postgres.PROJECT_REF@POOLER_HOST:5432/postgres'
DATABASE_PASSWORD='CONTRASENA_PRIVADA_DE_LA_BASE'
DATABASE_POOL_MODE=session
```

Obtener usuario/host reales desde **Connect → Session pooler** de Supabase; no componerlos a mano ni dejar los marcadores del ejemplo. La contraseña puede ir separada para evitar errores con caracteres reservados. Este archivo se lee sin interpolar secuencias `${...}` de su contenido. No contiene la clave de login de Compilando: es la credencial de PostgreSQL.

Elegir `DATABASE_BACKEND=supabase` en el `.env` personal. Verificar e iniciar:

```bash
uv run flask --app compilando:create_app database-info
uv run flask --app compilando:create_app check-db
uv run flask --app compilando:create_app run --port 5051
```

`database-info` muestra la selección para ese comando sin conectar ni revelar credenciales; no inspecciona otro servidor que ya esté corriendo. `check-db` ejecuta solo `SELECT 1`, sin crear tablas. Si falta el perfil, se avisa al arrancar y no se cambia silenciosamente a SQLite. Si el perfil existe pero el proyecto está pausado o la contraseña es incorrecta, la comprobación falla: elegir SQLite debe ser una decisión explícita.

La base compartida del equipo ya se preparó anteriormente. No ejecutar migraciones de una rama distinta sobre esa base por rutina ni para corregir un fallo de red. Esta rama puede tener un historial diferente al de `developer`; las revisiones remotas se coordinan antes de aplicarlas.

## Compatibilidad de configuración

Las variables ya exportadas en una terminal prevalecen sobre `.env` al usar Flask.

Compatibilidad: si no se define `DATABASE_BACKEND`, se usa `auto`: conserva el `DATABASE_URL` anterior y usa SQLite solo si no existe esa URL. Así no se cambia la conexión actual de quienes ya tenían Supabase configurado. No hay fallback automático ante errores de conexión.

## Precedencia del perfil Supabase

Con `DATABASE_BACKEND=supabase` se elige un conjunto de credenciales completo en este orden:

1. Variables `SUPABASE_DATABASE_URL`, `SUPABASE_DATABASE_PASSWORD` y `SUPABASE_DATABASE_POOL_MODE` si está definida la primera.
2. `DATABASE_URL`, `DATABASE_PASSWORD` y `DATABASE_POOL_MODE` de `.env.supabase.local`.
3. Las variables genéricas anteriores `DATABASE_URL`, `DATABASE_PASSWORD` y `DATABASE_POOL_MODE`, si apuntan a PostgreSQL.

No se mezcla la contraseña de un perfil con el usuario/host de otro. Por ejemplo, si se define `SUPABASE_DATABASE_URL`, también debe configurarse su contraseña en esa URL o en `SUPABASE_DATABASE_PASSWORD`; no se toma prestada del archivo de otro proyecto.

Las pruebas que pasan `SQLALCHEMY_DATABASE_URI` explícita a `create_app` tienen prioridad y continúan aisladas en sus bases temporales, aunque la computadora tenga seleccionado Supabase.

## Datos, archivos y trabajo en equipo

- Un pull trae código y `.env.example`; no configura credenciales privadas. No publicar `.env`, `.env.supabase.local`, respaldos ni la carpeta `instance/`.
- Si dos compañeros eligen el mismo proyecto Supabase, trabajan sobre los mismos registros. SQLite es independiente para cada copia local.
- Este selector elige la conexión SQL; no incorpora funciones ni adaptadores de archivos de otras ramas. En esta versión, avatares y adjuntos todavía utilizan carpetas locales: sus bytes no se transfieren al cambiar de base ni están automáticamente disponibles en otra computadora.
- `database-info` informa el modo elegido. Un `--port` alternativo permite elegir otro puerto si hace falta, pero no convierte dos bases en una sola ni sincroniza sesiones.
- No hace falta crear otra organización, contratar servicios ni habilitar facturación para usar el selector.

Referencia: [métodos de conexión PostgreSQL en Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres).
