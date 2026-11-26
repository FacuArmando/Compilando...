# Rendimiento: navegación con Supabase

Fecha: 26/11/2026. Trabajo local en `matibranch`; sin operaciones Git, deploy, servicios pagos ni cambios del esquema de la aplicación.

## Medición antes/después

Se ejecutaron los mismos recorridos de Flask contra Supabase real con 25 preguntas, 75 respuestas, tres usuarios y dos etiquetas de prueba. Se utilizó un esquema privado nuevo dentro de una transacción, revertida al terminar cada ensayo. Se comprobó que el esquema desapareciera: no se alteraron cuentas, sesiones, votos ni publicaciones reales. No se llamó a IA.

Cada ensayo tuvo tres recorridos. La tabla muestra su mediana, con conexiones ya abiertas y actividad de sesión reciente. Es una muestra pequeña para orientar esta tanda, **no un p95 ni una garantía de latencia**. Se usó el cliente de pruebas de Flask con contextos nuevos por solicitud: incluye el backend y la red hacia Supabase, pero no descargas ni renderizado del navegador. Los savepoints de aislamiento añaden trabajo de control; las comparaciones deben hacerse entre estos mismos ensayos.

| Recorrido | Antes | Después | Reducción aproximada | Ejecuciones SQL antes → después |
| --- | --- | --- | --- | --- |
| Login | 1.915 ms | 1.664 ms | 13% | 6 → 4 en intentos posteriores |
| Inicio autenticado | 1.665 ms | 1.269 ms | 24% | 6 → 5 |
| Perfil | 1.853 ms | 720 ms | 61% | 7 → 2 |
| Refresco de estadísticas | 1.402 ms | 843 ms | 40% | 5 → 2 |
| Detalle de pregunta | 3.836 ms | 1.509 ms | 61% | 16 → 6 |

El primer intento de login del ensayo pasó de 3.089 a 2.067 ms y de 8 a 6 ejecuciones SQL. No confundirlo con apertura fría de conexión: esa conexión ya estaba abierta para preparar el ensayo. Las cifras de SQL cuentan SELECT/INSERT/UPDATE/DELETE, sin sumar savepoints de aislamiento como consultas de negocio.

Una consulta mínima `SELECT 1` tardó unos 353–355 ms desde la app, frente a 0,027–0,047 ms de ejecución reportada por PostgreSQL. La apertura inicial de la conexión tomó aproximadamente 2,8–3,0 s. Esto muestra que los viajes y la conexión pesan mucho; no demuestra que cada consulta compleja tarde lo mismo ni que todos los clics dependan de SQL.

## Cambios aplicados

### Tercera tanda: costo real de red y listado

Ante el reporte de lentitud persistente, se midió el servidor que Mati inició manualmente. `/health` respondió en 16 ms; dos lecturas anónimas de `/` tardaron 1.302 y 1.328 ms. No se inició ni detuvo ningún servidor.

En otro proceso de diagnóstico, una conexión PostgreSQL nueva tardó 3.144 ms en abrirse. En tres ciclos posteriores sobre el pool ya abierto, `SELECT 1` tuvo estos costos:

| Etapa | Intervalo observado |
| --- | --- |
| Obtener/comprobar la conexión reutilizada | 184–267 ms |
| Ejecutar la primera consulta de la transacción | 352–395 ms |
| Cerrar y devolver la conexión, incluyendo rollback | 171–180 ms |
| Ciclo completo | 720–812 ms |

Estos valores incluyen protocolo y transacciones; no son el tiempo de ejecución SQL dentro de PostgreSQL ni un ping puro. Incluso una consulta mínima tiene una espera considerable desde esta computadora hacia el pooler remoto. El problema no se explica por el volumen del listado ni se soluciona solo cambiando la animación de carga. El contexto medido es Flask local y Supabase en la costa este de EE. UU.

Se eliminaron otras dos consultas del inicio: las etiquetas usan carga conjunta y el total filtrado se obtiene con `COUNT(*) OVER ()` en la consulta paginada. SQLAlchemy aplica el límite a las preguntas antes de unir etiquetas y elimina duplicados al construir los objetos. Se mantienen veinte tarjetas, páginas, conteos, filtros y preguntas sin etiquetas. No se agregaron columnas físicas ni caché de datos privados.

Se compararon ambas implementaciones en memoria contra Supabase, alternando una con otra, sin cookies de usuarios ni escrituras. Tras un calentamiento por variante, las cuatro muestras de inicio anónimo dieron:

| Variante | Consultas SELECT | Mediana |
| --- | --- | --- |
| Antes de esta tanda | 4 | 1.470 ms |
| Después | 2 | 950 ms |

La reducción observada es aproximadamente 35%; la muestra es pequeña y no mide renderizado del navegador. Con sesión reciente, las pruebas aisladas exigen como máximo tres lecturas, incluida la validación de identidad. También se probó pipeline de Psycopg con consultas mínimas, sin una ventaja suficiente para justificar incorporarlo.

Verificación de esta tanda: 66 pruebas aprobadas de listados, navegación, sesiones y configuración, más Ruff y formato. La regresión nueva comprueba preguntas con ocho etiquetas y otras sin ninguna, sin duplicar el total ni recortar las páginas. Para cargar estos cambios, Mati debe reiniciar manualmente su Flask si lo inició sin recarga automática.

La latencia remota sigue pendiente: para trabajar localmente se puede elegir SQLite; para evaluar el producto con Supabase hay que medir Flask desplegado cerca de la base. Vercel recomienda ubicar las funciones junto a la fuente de datos y documenta `iad1` como región predeterminada de nuevos proyectos ([regiones de funciones](https://vercel.com/docs/functions/configuring-functions/region)). Eso es una siguiente validación, no una garantía ni una autorización de deploy. Esta tanda no cambia la base seleccionada, regiones ni configuración privada.

### Perfil y estadísticas

- Las cuatro métricas se calculan con subconsultas en un único SELECT, conservando exclusiones de IA, autores propios, personas únicas y porcentaje de respuestas aceptadas.
- La lectura de identidad incluye los campos pequeños del perfil que la pantalla necesita, evitando pedir fecha de nacimiento y biografía por separado. El hash de contraseña no se incluye en esa carga de navegación.
- Cuando corresponde registrar actividad, se restauran en el objeto ORM solo los campos de identidad que ya se leyeron en esa solicitud. No se cambia globalmente `expire_on_commit` ni se cachea autorización entre solicitudes.
- El catálogo y los avatares públicos no autentican ni renuevan sesiones. Las operaciones privadas continúan comprobando la sesión en la base.

### Inicio y detalle

- El conteo de respuestas viaja con las preguntas de la página mediante una expresión calculada del ORM. En la tercera tanda también se incorporaron el total filtrado y las etiquetas a esa lectura. No agrega una columna física ni una migración. Se conserva la paginación de 20 preguntas, el orden y los filtros.
- El detalle carga autor, categoría, etiquetas, adjuntos y autores de respuestas de forma explícita. No dispara una consulta por respuesta para mostrar nombres o avatares.
- Las preguntas relacionadas se limitan a cinco en SQL, con conteos agregados; no se lee el historial entero ni los cuerpos de respuestas relacionadas para contarlas.

### Login y límites

- Cada contador usa UPSERT atómico de SQLite/PostgreSQL, eliminando el intento UPDATE seguido de INSERT y los savepoints por cada clave nueva.
- IP y cuenta siguen evaluándose en orden y contra la base compartida. Si se bloquea por IP, no se consume innecesariamente el contador de otro correo.
- La ventana vencida se reinicia en el propio UPSERT, aunque todavía no toque limpiar registros antiguos. Se conservan máximo, saturación y `Retry-After`.
- La limpieza de contadores viejos y sesiones vencidas hace más de un día se amortiza: ocurre al llegar un intento de autenticación cuando vence el intervalo de mantenimiento, como máximo de 15 minutos por proceso. No se hace en cada login.
- La marca en memoria solo decide cuándo limpiar; no guarda permisos ni reemplaza los contadores compartidos. Se actualiza después del commit; ante fallo, la limpieza puede reintentarse.
- Se conserva el hash seguro de contraseñas y la revocación de sesiones.

### Recursos y respuesta visual

- Los avatares públicos conservan su caché de una hora y sus respuestas condicionales; cuenta y páginas privadas siguen con `no-store`. En esta rama, los bytes de avatar todavía son archivos locales.
- El perfil no vuelve a pedir sus estadísticas inmediatamente después de recibirlas en el HTML. El refresco pasa de 15 a 30 segundos, se pausa con la pestaña oculta y no solapa peticiones.
- Ese refresco sigue requiriendo autenticación, pero no mantiene viva por sí solo una sesión que el usuario dejó inactiva.
- Los números iniciales del perfil conservan el valor enviado por el servidor, en lugar de reiniciarse a cero y animarse durante 850 ms. Los cambios posteriores tienen una transición breve de 250 ms y respetan movimiento reducido.

## Verificaciones

- Suite completa: 492 pruebas aprobadas antes del último ajuste de conservación de identidad.
- Tras ese ajuste: 123 pruebas específicas aprobadas, incluyendo la nueva prueba de perfil con renovación de actividad y comprobación de permisos en la siguiente solicitud.
- Regresiones nuevas para presupuestos de consultas, estadísticas correctas, contadores sin savepoints, ventanas que vencen sin limpieza y reintento tras rollback.
- Se conservaron las pruebas de límites concurrentes, límites entre instancias, CSRF, revocación, contraseñas y orden/paginación.
- Ruff, formato y sintaxis JavaScript aprobados. Simulación del refresco de estadísticas: sin llamada inicial duplicada, sin solapamiento, sin consulta oculta y con actualización al restaurar el historial.
- El servidor real de `127.0.0.1:5051` respondió 200 para inicio, salud y catálogo. Se comprobó una carga posterior a la inicial; no se operó el navegador del usuario.

## Qué sigue pendiente

- El módulo de MG/feedback no está en el checkout actual. No se midió ni modificó su endpoint; estas cifras no representan votar. No traerlo de otra rama sin el flujo Git del usuario.
- Medir más muestras, p95 y el recorrido completo del navegador con Mati; separar tiempo del servidor, red, recursos y percepción visual.
- El login conserva más viajes indispensables que las lecturas. Su mejora actual es menor que la de perfil/detalle; no declarar que ya es instantáneo.
- Evaluar las consultas que sigan siendo costosas con planes de ejecución, sin agregar índices por intuición ni reducir seguridad.
- Mantener presente la distancia de red: Flask local con PostgreSQL remoto tiene una espera que no se elimina con animaciones. SQLite es el modo rápido para desarrollar sin depender de esa red; Supabase permite probar la integración compartida. El selector no cambia de base automáticamente.
- Si se retoma el deploy, medir app y base cercanas entre sí antes de sacar conclusiones sobre la experiencia desplegada. Este trabajo no autoriza publicar ni cambiar regiones.
