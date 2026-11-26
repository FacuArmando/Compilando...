# Primera conexión de Compilando con Supabase

Parte de Mati. Fecha: 26/11/2026. **Supabase ya está preparado para usar la app con cuentas nuevas.** Historial aplicado hasta `d9e5f6a712b3`: 13 tablas de aplicación y `alembic_version`. Se adaptó la búsqueda Unicode y se agregó almacenamiento persistente de avatares/adjuntos dentro de PostgreSQL. `.env` quedó configurado para usar Supabase al reiniciar el servidor; no se importaron los datos de SQLite. Ver [pasos actuales de uso y deploy](deploy-gratis.md).

**Presupuesto confirmado: costo adicional cero.** Compilando se crea en una organización **Free**. La organización Pro que Mati ya usa queda fuera de esta tarea. No contratar compute, upgrades, add-ons ni ampliar cuotas pagas.

## 1. Crear el proyecto

1. Si el formulario muestra una organización **Pro**, cancelar esa creación. Un proyecto adicional ahí tiene compute facturable incluso en reposo; no suponer que los créditos existentes garantizan costo cero.
2. Usar el enlace **Create a free organization** del formulario o crear una organización desde el selector del Dashboard, eligiendo **Free**. No modificar la organización Pro existente.
3. Confirmar disponibilidad de cupo: Supabase permite dos proyectos Free activos, con el cómputo del cupo según las organizaciones de las que se es Owner/Administrator. Una organización nueva no reinicia ese cupo. Si está agotado, detenerse; no actualizar un plan, borrar ni trasladar proyectos por iniciativa propia.
4. Dentro de la organización Free, elegir **New project**, con un nombre como `compilando-preview`.
5. Generar una contraseña de base de datos y guardarla en un gestor de contraseñas. Es distinta de una API key.
6. Elegir la región próxima a la función de Vercel. Si se conserva la región predeterminada de Vercel en Virginia, elegir US East / N. Virginia en Supabase; si se elige otra región para la app, coordinar ambas.
7. Revisar el resumen antes de confirmar: plan **Free**, sin compute ni complementos pagos. Si aparece un cargo mensual o por hora, no confirmar.
8. Crear el proyecto gratuito y esperar a que la base esté disponible. No crear tablas a mano.

El plan Free tiene cuotas y puede pausarse tras un período de baja actividad de aproximadamente siete días. Se acepta esa limitación para esta primera demo; no contratar un plan para evitar la pausa ni prometer disponibilidad continua.

Referencias: [mantener proyectos Free teniendo Pro](https://supabase.com/kb/troubleshooting/keeping-free-projects-after-pro-upgrade-Kf9Xm2), [facturación y cupo gratuito](https://supabase.com/docs/guides/platform/billing-on-supabase), [pausas por inactividad](https://supabase.com/docs/guides/platform/free-project-pausing).

## 2. Mantener el acceso a datos detrás de Flask

En el Dashboard, abrir la configuración/integración **Data API** y desactivar **Enable Data API** si no se utiliza. Su estado en este proyecto no está confirmado. Para crear las tablas sin depender de ese ajuste, se aplicó una protección SQL verificable en la misma transacción que todo el historial.

Compilando usa PostgreSQL mediante SQLAlchemy desde Flask. Su autenticación y sus permisos actuales siguen en la aplicación. La revisión `b7f3c2a19d60` habilita RLS sin políticas en las 13 tablas, revoca todos los permisos de tablas y sus secuencias a `PUBLIC` y a los roles existentes `anon`, `authenticated` y `service_role`. El propietario SQL conserva acceso. Se comprobó que los tres roles de API no pueden leer usuarios, incluso si Data API sigue habilitada. La migración es un no-op en SQLite y no modifica las tablas internas de Supabase.

Esta revisión protege una lista fija de tablas actuales. Cada tabla futura debe incluir su protección en la migración que la crea. No asumir que hereda RLS. Su downgrade conserva las restricciones intencionalmente; no reabre permisos desconocidos.

No cambiar permisos globales a públicos ni crear políticas que permitan todo para resolver una conexión. La configuración de Storage se hará en la parte de Facu; no hace falta habilitar acceso público a las tablas de la app para guardar objetos.

Referencias oficiales: [desactivar la Data API](https://supabase.com/docs/guides/api/securing-your-api#disable-the-data-api), [RLS](https://supabase.com/docs/guides/database/postgres/row-level-security).

## 3. Obtener la conexión para la primera prueba local

1. En el proyecto, abrir **Connect**.
2. Seleccionar **Session pooler**, normalmente en el puerto `5432`.
3. Copiar su cadena de conexión de PostgreSQL al archivo local indicado abajo, nunca al chat.

Para esta etapa local usamos Session pooler, que permite conexión por IPv4. Para la función de Vercel prepararemos el perfil **Transaction pooler**, normalmente puerto `6543`. Las migraciones se harán con conexión directa cuando esté disponible o con el método de sesión apropiado; no cambiar de modo a ciegas.

Referencias: [métodos de conexión](https://supabase.com/docs/guides/database/connecting-to-postgres), [SQLAlchemy en Supabase](https://supabase.com/kb/troubleshooting/using-sqlalchemy-with-supabase-FUqebT).

## 4. Completar el perfil local privado

Se preparó `.env.supabase.local`, excluido por la regla `.env.*` del `.gitignore` existente. No publicarlo ni adjuntarlo a una conversación. El `.env` habitual queda intacto.

Completar únicamente en el editor local:

```dotenv
# Ejemplo ficticio: reemplazar host y referencia por los de Connect.
DATABASE_URL=postgresql://postgres.PROJECT_REF:[YOUR-PASSWORD]@POOLER_HOST:5432/postgres
DATABASE_PASSWORD="CONTRASENA_REAL_SOLO_EN_EL_ARCHIVO_PRIVADO"
DATABASE_POOL_MODE=session
```

- Puede quedar el marcador `[YOUR-PASSWORD]` en la URI: `DATABASE_PASSWORD` lo sustituye en memoria.
- La contraseña separada permite caracteres como `@`, `/` y `#` sin codificarlos como parte de una URL.
- Si la contraseña incluye comillas o secuencias especiales de archivos dotenv, guardarla con el escapado correspondiente. No pedir ayuda pegando su valor.
- También se acepta una URI completa con la contraseña correctamente codificada; en ese caso dejar `DATABASE_PASSWORD` vacío para no sobreescribirla.
- Se aceptan los prefijos `postgres://`, `postgresql://` y `postgresql+psycopg://`; la aplicación elige el controlador Psycopg 3 instalado.
- La conexión requiere TLS por defecto. No agregar `sslmode=disable` para intentar resolver problemas de red.
- No poner `APP_ENV=production` en esta primera prueba local. La publicación y sus dominios se configuran después.

El perfil se carga solo al elegirlo explícitamente. No modificar `DATABASE_URL` del `.env` habitual hasta completar la prueba y decidir qué entorno se quiere usar al desarrollar.

## 5. Qué hace el código preparado

| Archivo | Responsabilidad |
| --- | --- |
| `compilando/database.py` | Procesa la configuración final, elige Psycopg 3, aplica TLS y ajusta el modo de pool |
| `compilando/config.py` | Lee `DATABASE_URL`, contraseña separada y modo |
| `compilando/__init__.py` | Aplica esa preparación después de overrides; no crea carpetas locales al arrancar con PostgreSQL |
| `compilando/commands.py` | Agrega `check-postgres`, una consulta de lectura que rechaza el fallback SQLite |
| `pyproject.toml`, `uv.lock` | Incluyen Psycopg 3 con distribución binaria |
| `tests/test_database_config.py` | Comprueba configuración, aislamiento, TLS y errores sin credenciales ni conexiones reales |
| `migrations/env.py` | Admite una conexión externa para aplicar y comprobar todo el historial dentro de una transacción |
| `migrations/versions/b7f3c2a19d60_proteger_tablas_backend_postgresql.py` | Protege las tablas actuales contra el acceso desde los roles de la API |
| `tests/test_database_migrations.py` | Comprueba esquema completo y rollback de una migración con conexión externa en SQLite temporal |

`DATABASE_POOL_MODE` admite `direct`, `session` y `transaction`. En modo transacción se usa `NullPool` y se desactiva la preparación automática de sentencias para la compatibilidad con el pooler. No hay una conexión remota al importar/crear la app: se abre cuando se ejecuta una consulta.

## 6. Comprobar la conexión

Con el proyecto disponible y el perfil privado completo, se puede repetir esta consulta de lectura; no cambia las tablas existentes:

```bash
uv run flask --env-file .env.supabase.local --app compilando:create_app check-postgres
```

Resultado esperado:

```text
Conexión PostgreSQL: OK. No se crearon tablas ni se copiaron datos.
```

El comando falla si sigue usando SQLite; no informa éxito por conectarse a otra base local. Los errores controlados no muestran la URL completa ni la contraseña.

Flask da prioridad al perfil sobre `.env`, pero las variables ya exportadas en la terminal tienen prioridad sobre ambos. Si hay un `DATABASE_URL` exportado previamente, revisar ese entorno antes de comprobar o migrar. No imprimir la variable completa para diagnosticarlo.

## 7. Estado comprobado y siguiente paso

La inicialización anterior aplicó el historial desde cero en una transacción. Luego se aplicaron las revisiones de búsqueda y archivos; se contrastó el esquema contra los modelos sin diferencias y se comprobaron RLS y ausencia de permisos de API.

El recorrido HTTPS sobre Supabase mediante Transaction pooler (`6543`) pasó registro con ingreso automático, CSRF, publicación con adjunto, descarga, búsqueda por acentos/ñ/C++, autocompletado, Guardadas, avatar, IA con proveedor simulado y evaluación de utilidad. Los datos de prueba se revirtieron; la base queda vacía para cuentas nuevas. No se llamó a Gemini real.

Pasaron 585 pruebas Python, 25 de JavaScript, Ruff y formato. Las pruebas de archivo verifican persistencia tras cerrar/reabrir la conexión, reemplazo, rollback, cupo y cascada sin escribir archivos en el disco del servidor.

El paso pendiente es el deploy real y la revisión de su URL. La guía actual es [deploy-gratis.md](deploy-gratis.md). `.env.vercel.local` contiene el perfil privado preparado; no publicarlo ni copiarlo al chat. Desactivar Data API si no se usa sigue siendo una simplificación adicional; el bloqueo SQL ya protege las tablas actuales.

No usar `db.create_all()` ni importar usuarios/sesiones locales. Si una futura migración falla, revisar la revisión realmente persistida antes de repetir; no ejecutar downgrade, borrar tablas ni restaurar permisos automáticamente.
