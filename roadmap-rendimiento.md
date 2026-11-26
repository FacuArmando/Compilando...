# Roadmap de rendimiento de Compilando

Fecha: 26/11/2026. Responsable: Mati, con Codex. Estado: **en curso; tandas de sesiones, navegación, estadísticas y login implementadas y medidas en `matibranch`**.

## Objetivo y alcance

**Última tanda, 26/11:** el inicio anónimo pasó de 4 a 2 lecturas y de 1.470 a 950 ms de mediana en cuatro muestras alternadas contra Supabase. Con sesión reciente, el presupuesto baja de 5 a 3 lecturas. Pasaron 66 pruebas específicas. Una consulta mínima con comprobación de conexión y cierre todavía tarda 720–812 ms desde esta Mac: la navegación remota no está resuelta por completo. Ver [diagnóstico y límites de la medición](docs/rendimiento-mediciones.md). No se cambió la base activa ni se inició, detuvo o desplegó un servidor.

**El problema reportado es global: todas las pantallas y cada interacción se sienten lentas desde la conexión a Supabase. El like es un ejemplo, no el alcance del problema.** Recuperar una navegación ágil al abrir inicio, detalle, cuenta, Guardadas y formularios, y al buscar, publicar, guardar o valorar. Corregir primero las causas compartidas; conservar la seguridad y medir cada mejora.

Distinguir también los clics que deberían resolverse enteramente en el navegador (abrir un menú o un panel) de los que necesitan servidor. Si ambos se demoran, medir JavaScript, renderizado y recursos además del backend; no atribuir automáticamente todo a PostgreSQL.

- Trabajar en pasos pequeños, cada uno con un resultado comprobable antes de continuar.
- El usuario controla Git. Codex no cambia ramas, integra cambios, prepara archivos, crea commits ni publica.
- `main` conserva la versión anterior. Este documento no autoriza llevarle cambios ni desplegar en Vercel.
- Presupuesto adicional: **cero**. No contratar planes, Redis, servicios de caché, servidores ni ampliaciones pagas.
- No cambiar de proveedor, región o arquitectura como primer intento. Primero medir y corregir las solicitudes actuales.
- No leer ni publicar contraseñas, cookies, tokens, URLs privadas o parámetros SQL con datos personales.

## Advertencia sobre la versión de trabajo

Al preparar este archivo, el checkout actual contiene las rutas tradicionales de respuestas y el control de sesiones, pero no aparecen `modules/answers/feedback.py`, el módulo de Guardadas ni los archivos de preparación de Supabase revisados antes. **No se consultó Git ni se cambió de rama.**

Antes de implementar, el usuario debe tener abierta la versión que realmente reproduce el problema. Las referencias a likes, almacenamiento PostgreSQL y actualización automática del feed corresponden a la versión revisada en la conversación; hay que confirmar sus rutas en ese checkout. No reconstruir funciones ausentes ni integrar ramas como parte de una optimización.

La rama actual se confirmó mediante lectura del archivo HEAD, sin ejecutar comandos Git ni modificar su estado: `matibranch`. La primera tanda modifica únicamente el control de sesión y el catálogo, que sí están presentes en esta versión. No se trajeron los módulos ausentes de `developer` ni se modificó `main`.

**Incidencia de arranque corregida:** el `.env` local ya apuntaba a Supabase con `DATABASE_PASSWORD` separada, pero esta rama no la aplicaba. Se reprodujo el rechazo por contraseña ausente, se incorporó su lectura con Psycopg 3/TLS y se añadió la dependencia reproducible. Las pruebas SQLite siguen aisladas mediante overrides. Pasaron 119 pruebas de configuración, factory, sesiones y login; además, una instancia con el perfil real de Supabase devolvió 200 en inicio, login y catálogo. No se alteró el esquema ni se importaron datos. Esta compatibilidad de conexión no incorpora automáticamente Guardadas, likes, búsqueda normalizada ni almacenamiento PostgreSQL de otras ramas.

**Selector para el equipo:** `DATABASE_BACKEND` del `.env` permite elegir SQLite o Supabase; el servidor se inicia y detiene manualmente con Flask. `database-info` muestra la selección y `check-db` comprueba la conexión. El selector no escribe perfiles ni mueve datos. Ambas conexiones pasaron `SELECT 1`; durante la validación, la aplicación devolvió 200 con Supabase. Se conserva compatibilidad `auto` para las configuraciones anteriores. Ver [cómo cambiar de base](docs/cambiar-base.md). Esto facilita trabajar y comparar motores; no sustituye las optimizaciones de rendimiento pendientes.

### Primera tanda completada: sesiones y catálogo

- En solicitudes autenticadas con actividad reciente, se consulta la identidad vigente sin escribir `ultimo_acceso` ni hacer commit solo por navegar.
- La consulta inicial incluye los datos de identidad que usa la interfaz, incluido el nombre del avatar, y evita cargar el hash de contraseña cuando no se necesita.
- La actividad se registra como máximo una vez cada 30 segundos por sesión cuando hay solicitudes. La actualización condicional evita sobrescribir actividad más reciente de otra solicitud. No se cachea la autorización entre solicitudes.
- El timeout de inactividad no se amplía: puede adelantarse hasta 30 segundos respecto del último clic real. Para timeouts configurados más cortos, el intervalo se limita al 10% de ese timeout. El vencimiento absoluto conserva su límite.
- El catálogo de traducciones, común a todos los usuarios, omite la autenticación, conserva `public, max-age=3600` y responde 304 con ETag cuando corresponde. No renueva actividad ni crea cookies. Las páginas privadas conservan `no-store`.
- Verificación: **163 pruebas** de autenticación, sesiones, interfaz y rendimiento aprobadas, además de Ruff y formato. No se consultó ni modificó Supabase en esta tanda; no se ejecutó IA.

| Solicitud de prueba | Antes | Después |
| --- | --- | --- |
| Identidad para interfaz con actividad reciente | 4 ejecuciones SQL y 1 commit | 1 SELECT y 0 commits |
| Catálogo con cookie de sesión, reloj de prueba sin avance | 1 SELECT y 1 commit | 0 consultas y 0 commits |
| Catálogo con ETag coincidente | Sin soporte condicional | 304 sin cuerpo ni consultas |

Estos resultados corresponden a una ruta de prueba de identidad y al catálogo, sobre SQLite temporal. No son el conteo total del inicio ni una medición de latencia de Supabase. La medición end-to-end sobre la versión conectada sigue pendiente; no declarar resuelta la lentitud global todavía.

## Punto de partida: hechos e hipótesis

**Actualización de la segunda tanda:** se midió Supabase con datos aislados reversibles y se optimizaron perfil, inicio, detalle, login, avatares y refrescos. Medianas de tres muestras: perfil 1.853 → 720 ms; detalle 3.836 → 1.509 ms; inicio 1.665 → 1.269 ms; login 1.915 → 1.664 ms. Ver [metodología, cambios y límites](docs/rendimiento-mediciones.md). No son p95 ni tiempos de MG. Sigue pendiente la aceptación en el navegador y la optimización del módulo de MG, ausente en este checkout.

Medición anterior sobre la versión conectada a Supabase, con páginas anónimas y sin llamadas a IA:

| Recorrido | Resultado observado |
| --- | --- |
| Inicio | Dos muestras de 1.745 ms y 1.581 ms; 6 ejecuciones SQL por solicitud |
| Tiempo acumulado de esas ejecuciones SQL | Aproximadamente 1.216–1.255 ms |
| Ejecución SQL típica en el inicio | Mediana de 172–179 ms, incluyendo red y espera del cliente |
| Login anónimo | 16 ms, sin consultas SQL |
| Primera apertura + `SELECT 1` + devolución de conexión | 3.266 ms en una muestra |
| Mismo ciclo con conexión reutilizada | 689–693 ms en tres muestras |
| Like autenticado | Lentitud reportada por Mati; **todavía sin medición propia** |

Estas muestras no son percentiles ni una prueba de carga. El ciclo de conexión incluye checkout, comprobaciones y cierre de transacción: no equivale al tiempo de ejecución de `SELECT 1` dentro de PostgreSQL.

Hallazgos del código revisado:

- El control de sesión consulta la cuenta, actualiza `ultimo_acceso` y hace commit en cada solicitud autenticada, excepto las rutas expresamente excluidas.
- Un commit puede expirar objetos ORM y provocar nuevas lecturas al usarlos después. Hay que contar esas lecturas antes de cambiar el comportamiento global de SQLAlchemy.
- La política general de respuestas sobrescribe la caché con `no-store` salvo para `static`; alcanza recursos que podrían tener otra política, como el catálogo y los avatares públicos.
- En la versión con Supabase, los avatares se leen desde PostgreSQL y pueden añadir solicitudes independientes a la carga de una pantalla.
- En esa versión, el feed consulta su estado cada cinco segundos. El endpoint también tiene una vía de procesamiento automático de IA condicionada por configuración: verificar si está activa, sin invocar Gemini durante el diagnóstico.

Hipótesis principal: varios viajes secuenciales de red explican una parte importante de la espera. Aún hay que separar esa demora de apertura de conexiones, bloqueo de escrituras, renderizado y tiempo real del motor.

## Orden de trabajo

| Paso | Entrega significativa | Prioridad |
| --- | --- | --- |
| 0 | Diagnóstico global: navegación, acciones y clics locales | Inmediata |
| 1 | Menos trabajo compartido de sesión por solicitud | Inmediata |
| 2 | Menos consultas en inicio, detalle, cuenta y Guardadas | Inmediata |
| 3 | Recursos, avatares y catálogo sin cargas repetidas | Inmediata |
| 4 | Escrituras ágiles y seguras: likes y Guardadas | Alta |
| 5 | Respuesta visual inmediata de los controles | Alta |
| 6 | Actualización del feed sin trabajo excesivo de fondo | Alta |
| 7 | Ajustes específicos de conexiones e índices según evidencia | Posterior |
| 8 | Comparación global y recorrido manual con Mati | Cierre |

No empezar todas las tandas juntas. El primer bloque es **0 → 1 → 2**, priorizando el cuello de botella compartido que confirme la medición. Si el problema está en apertura/reutilización de conexiones, adelantar ese ajuste del paso 7; si está en JavaScript o recursos, adelantar la corrección pertinente del paso 3/5. No optimizar solo el endpoint del pulgar ni limitar el trabajo a disimular su espera con una animación.

## Paso 0 — localizar la lentitud general

- [ ] Confirmar que el checkout y el servidor que usa Mati contienen los likes y la conexión a Supabase.
- [ ] Hacer un mapa de recorridos: inicio → detalle → cuenta → Guardadas → formulario, búsqueda y acciones de escritura. Identificar rutas, solicitudes auxiliares y recursos que se repiten.
- [ ] Incluir clics locales: abrir menú, desplegar un panel, cambiar tema/idioma. Comprobar si esperan red innecesariamente, si hay tareas JavaScript largas o trabajo de renderizado que bloquea el navegador.
- [ ] Medir por separado: clic → respuesta visual, clic → respuesta HTTP y clic → estado confirmado.
- [ ] Registrar cantidad y tiempo de SQL, conexiones nuevas/reutilizadas, commits y rollbacks. No registrar valores de parámetros ni contenidos de archivos.
- [ ] Separar primera carga y cargas posteriores; medir también con sesión iniciada y como visitante.
- [ ] Tomar unas 20 muestras secuenciales por recorrido después del calentamiento, con cuentas/contenido de prueba. Registrar mediana y percentil 95 con el tamaño de muestra.
- [ ] Medir inicio, detalle, cuenta, Guardadas, formularios, búsqueda, publicación, like, retirar/cambiar valoración y avatar. Las escrituras usan registros de prueba y no alteran contenido de personas reales.
- [ ] Desglosar espera del HTML/JSON, descarga de recursos y momento en que la pantalla se vuelve utilizable. Separar viajes de red, conexión/pool, SQL, transacciones, renderizado del servidor y trabajo del navegador.
- [ ] Comparar solicitudes autenticadas y anónimas que comparten la misma vista, con el refresco de fondo activo/inactivo en una prueba controlada.
- [ ] Comparar SQL instrumentado con la pestaña Network cuando Mati pruebe en su navegador. No operar su navegador sin autorización.

**Cierre:** tabla de recorridos antes de cambios y causa compartida dominante identificada con evidencia. El desglose del like forma parte de esa tabla, junto con navegación y controles locales. No atribuir toda la espera al plan gratuito sin evidencia.

## Paso 1 — quitar trabajo repetido del control de sesión

Referencias confirmadas en el checkout actual: `compilando/modules/auth/sessions.py`, `compilando/modules/auth/security.py` y `compilando/i18n.py`.

- [x] Cargar únicamente los datos de sesión/cuenta necesarios y detectar lecturas adicionales después del commit. Tanda 1: lectura común reducida de 4 ejecuciones SQL a 1 cuando no corresponde actualizar actividad.
- [ ] Definir qué recursos son realmente públicos e independientes de la sesión. Evitar autenticar una imagen pública o un catálogo estático si no necesitan conocer al usuario.
- [x] Revisar la actualización de `ultimo_acceso`: evitar una escritura y un commit en cada solicitud cuando el acceso ya se registró recientemente. Cadencia de 30 segundos y UPDATE condicional.
- [x] Definir una cadencia corta y documentar su efecto sobre el vencimiento por inactividad. No extender silenciosamente la duración de sesión ni tratar una cookie como prueba suficiente de autorización. Tolerancia conservadora documentada arriba.
- [x] Mantener la verificación de revocación y de permisos en operaciones privadas. No cachear usuarios autenticados globalmente entre solicitudes. Pruebas verifican cambios entre solicitudes consecutivas.
- [ ] Evitar duplicar transacciones cuando la operación necesita una escritura propia; delimitar claramente quién confirma cada cambio. Tanda 2: mantenimiento de autenticación amortizado y UPSERT atómico; faltan los recorridos de MG/Guardadas de la versión que los contiene.
- [ ] No desactivar globalmente `expire_on_commit` para ocultar consultas sin revisar la consistencia de las cuentas y permisos.
- [x] Probar logout, sesión revocada, vencimiento, cambio de contraseña y dos clientes concurrentes. Suite de autenticación aprobada junto con las nuevas regresiones de rendimiento.

**Cierre:** navegar entre pantallas y ejecutar acciones privadas hace menos trabajo repetido de autenticación, con las mismas garantías de seguridad. Registrar viajes y commits eliminados en inicio, detalle, cuenta, Guardadas y like.

## Paso 2 — consultas de todas las pantallas

- [ ] Medir inicio, detalle, cuenta, Guardadas y formularios; incluir una página representativa de 20 preguntas y varios autores.
- [ ] Revisar el trabajo común de menús, contexto de plantillas, categorías y estadísticas; no volver a consultar los mismos datos en cada componente de una pantalla.
- [ ] Evitar N+1: autores, categorías, etiquetas y estados de Guardadas se cargan por lote.
- [x] Agrupar conteos de respuestas y no cargar respuestas completas para contarlas. Tanda 2: el conteo del inicio viaja en la consulta de la página y el de relacionadas se agrega en SQL.
- [x] En el detalle, traer solo las preguntas relacionadas que se muestran y sus conteos, sin leer todo el historial. Límite SQL de cinco y carga explícita de relaciones.
- [x] Mantener paginación y orden estables. Revisar si cada conteo total se necesita, sin eliminar información de interfaz por conveniencia. Se conservan totales, filtros y páginas; regresiones aprobadas.
- [ ] Evaluar caché breve únicamente para agregados públicos, por ejemplo destacados semanales; definir invalidación, alcance y tolerancia a datos desactualizados.
- [ ] No cachear páginas autenticadas completas ni compartir estrellas, votos o datos de cuenta entre usuarios.

**Cierre:** consultas acotadas por pantalla; agregar autores/preguntas no aumenta una consulta por tarjeta. Búsqueda y paginación conservan sus resultados.

## Paso 3 — recursos y cargas repetidas

- [ ] Medir cascada de CSS, JavaScript, imágenes y catálogo, bytes transferidos, recursos que bloquean el primer render y cabeceras reales de caché.
- [ ] Medir solicitudes de imagen, consultas por avatar y peso de miniaturas. No asumir que el HTML listo significa que la pantalla ya responde bien.
- [ ] Asegurar que feed, menú y listados pidan miniaturas, sin cargar la versión ampliada ni los bytes de imágenes dentro de consultas generales de usuarios.
- [ ] Definir una política de caché específica para imágenes públicas con nombre/versionado y para el catálogo. Mantener `no-store` en cuenta, sesiones y datos privados.
- [ ] Agregar validación condicional con ETag/Last-Modified cuando aporte una mejora real; evitar volver a transferir bytes sin cambios.
- [ ] Acordar TTL y comportamiento al reemplazar/eliminar una imagen. No aplicar caché pública o `immutable` indiscriminadamente a contenido que debe desaparecer.
- [ ] Verificar que abrir otra pantalla no repita la autenticación y descarga completas de los mismos recursos.

**Cierre:** navegar por segunda vez reutiliza recursos cuando corresponde y no sirve datos privados desde una caché compartida.

## Paso 4 — escrituras: likes y Guardadas

Ubicación de referencia en la versión previa: servicio de feedback, ruta `/answers/<id>/feedback` y resumen de evaluaciones. Confirmar nombres al empezar.

- [ ] Dibujar el flujo real: autenticación → respuesta/permisos → valoración → contador → respuesta JSON.
- [ ] Aplicar el mismo diagnóstico a guardar/quitar una pregunta: detectar lecturas y commits repetidos, evitar recargas completas y conservar idempotencia.
- [ ] Reutilizar identificadores ya disponibles y eliminar lecturas duplicadas de usuario, respuesta y valoración.
- [ ] Evaluar un UPSERT de PostgreSQL basado en la clave única existente para escribir la elección explícita. Mantener la compatibilidad de las pruebas locales sin introducir SQL innecesario en otros motores.
- [ ] Conservar la semántica idempotente: enviar «sí» dos veces no suma dos likes ni invierte el estado. Definir aparte cambiar a «no» y retirar la elección.
- [ ] Preservar la regla vigente sobre valorar respuestas propias y el tratamiento de respuestas de IA.
- [ ] Calcular el contador y la elección confirmada sin repetir agregaciones ni cargar todas las evaluaciones.
- [ ] Confirmar la transacción antes de responder éxito. Devolver JSON pequeño, sin renderizar la página completa ni recargar el detalle para cambiar un pulgar.
- [ ] Mantener CSRF, permisos, restricciones de unicidad y recuperación ante conflictos concurrentes.
- [ ] Probar dos usuarios votando a la vez, dos envíos idénticos y cambiar/retirar la elección.

**Cierre:** el POST tarda menos y ejecuta menos viajes que en el paso 0, con contador y elección correctos después de recargar.

## Paso 5 — respuesta inmediata de controles e interacciones

- [ ] Asegurar que menús, paneles y controles locales respondan sin esperar operaciones remotas. Corregir tareas largas de JavaScript o renderizado solo si el perfil las demuestra.
- [ ] Mostrar estado de carga oportuno al navegar o enviar formularios, sin deshabilitar toda la pantalla.
- [ ] Aplicar de inmediato el estado visual y una animación pequeña del pulgar; respetar `prefers-reduced-motion`.
- [ ] Separar esa respuesta visual de la confirmación de guardado. Evitar esperar al servidor para iniciar la animación.
- [ ] Si se muestra un contador optimista, conservar el último estado confirmado y reconciliarlo con el JSON del servidor.
- [ ] Gestionar clics rápidos con una sola petición en vuelo por respuesta y, si hace falta, una última intención pendiente. No disparar una petición por cada clic ni permitir que una respuesta vieja pise una elección nueva.
- [ ] Ante un rechazo confirmado, restaurar el estado correspondiente y mostrar un mensaje accesible.
- [ ] Ante timeout o corte de red, informar que no se pudo confirmar: el servidor podría haber guardado el voto. Reconsultar/reintentar la elección explícita de forma segura, sin enviar un toggle ambiguo.
- [ ] No bloquear toda la tarjeta ni volver a descargar las respuestas para confirmar un like.
- [ ] Probar error de red, 401, 403, CSRF vencido, 429 si corresponde y error del servidor.

**Cierre:** objetivo de respuesta visual de hasta 100 ms en condiciones normales del dispositivo; persistencia correcta y recuperación comprobada. Esta mejora no sustituye la optimización del POST.

## Paso 6 — trabajo de fondo del feed

- [x] Perfil: evitar la consulta inicial duplicada, pausar actualizaciones ocultas, impedir solapamientos y no renovar actividad de sesión por el refresco de estadísticas. Intervalo de 30 segundos. Esto no completa las tareas del feed que siguen abajo.

- [ ] Confirmar si sigue existiendo el polling de cinco segundos y qué tareas ejecuta su endpoint.
- [ ] Separar consultar conteos de generar respuestas: un GET de estado debe ser ligero y no iniciar llamadas externas de IA.
- [ ] Pausar actualizaciones cuando la pestaña esté oculta y evitar solapar peticiones si una tarda más que el intervalo.
- [ ] Consultar solo las preguntas visibles que realmente necesitan actualización y detenerse cuando ya no haya pendientes.
- [ ] Usar intervalo razonable y backoff ante errores; mantener la posibilidad de volver a comprobar al recuperar foco.
- [ ] Si se conserva IA automática, planificar su ejecución explícitamente sin depender de visitas o likes. No agregar colas o cron pagos en esta tanda.

**Cierre:** dejar la pantalla abierta no multiplica solicitudes ni llamadas a Gemini; los likes no compiten con procesamiento externo iniciado por el refresco.

## Paso 7 — conexiones e índices, después de medir

- [ ] Verificar el perfil activo: Session pooler para desarrollo persistente y el perfil previsto para funciones si se retoma Vercel.
- [ ] Medir apertura TLS, espera del pool, comprobación de conexión y cierre de transacción. No confundir esos tiempos con ejecución del SQL.
- [ ] Revisar reutilización y límites sin abrir más conexiones de las permitidas. No trasladar configuraciones de un servidor local a funciones sin justificación.
- [ ] Mantener TLS y recuperación de conexiones caídas; no quitar controles de disponibilidad solo para mejorar una cifra.
- [ ] Examinar con `EXPLAIN` las consultas que sigan siendo lentas dentro de PostgreSQL. Usar `ANALYZE` solo en lecturas controladas; no ejecutar escrituras reales como supuesto diagnóstico.
- [ ] Crear índices mediante migraciones únicamente cuando el plan lo justifique; no indexar todas las columnas.
- [ ] Si se vuelve a evaluar el deploy, comparar una función cercana a la base con el recorrido desde la computadora de Mati. Esa prueba es una decisión posterior y no autoriza publicar ahora.

**Cierre:** distinguir red, pool y motor con evidencia; ninguna compra ni modificación de infraestructura innecesaria.

## Paso 8 — aceptación y cierre

- [ ] Repetir las mismas muestras del paso 0, con condiciones y datos comparables.
- [ ] Registrar mediana, p95, ejecuciones SQL, transacciones y errores; presentar primera carga por separado.
- [ ] Objetivo inicial: reducir al menos 30% la mediana de los recorridos lentos prioritarios (navegación y acciones), sin empeorar p95, seguridad ni consistencia. Identificar excepciones y su causa; no declarar el objetivo cumplido por mejorar solo el like. Revisar la meta si la red cambia; no prometer tiempos inferiores a los viajes indispensables.
- [ ] Mantener respuesta visual inmediata del pulgar y comprobar el estado después de recargar.
- [ ] Comprobar sesiones, permisos, CSRF, concurrencia, Guardadas, búsqueda y archivos con las pruebas pertinentes a los cambios.
- [ ] Usar IA simulada y registros de prueba. No ejecutar pruebas destructivas ni llamadas de carga contra Gemini real.
- [ ] Hacer una prueba concurrente pequeña, solo después de las mediciones secuenciales, y vigilar errores/espera del pool.
- [ ] Pedir a Mati que pruebe las acciones que sentía lentas. La aceptación final incluye esa experiencia, no solo números del backend.
- [ ] Documentar qué se mejoró, qué queda pendiente y cualquier tolerancia temporal introducida.

### Registro antes/después

| Recorrido y condición | Muestras | Mediana antes/después | p95 antes/después | SQL antes/después | Transacciones antes/después | Resultado funcional |
| --- | --- | --- | --- | --- | --- | --- |
| Menú/panel local | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |
| Cuenta y formularios | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |
| Búsqueda/autocompletado | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |
| Like autenticado | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |
| Cambiar/retirar valoración | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |
| Inicio autenticado | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |
| Detalle autenticado | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |
| Guardar/quitar pregunta | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |
| Avatar, primera carga y repetida | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |

**Siguiente baby step:** validar con Mati inicio → detalle → cuenta en el navegador con estas mejoras. El backend ya tiene una comparación controlada en Supabase; para medir y optimizar MG/Guardadas falta disponer de los módulos correspondientes en la rama de trabajo mediante el flujo Git del usuario. No declarar terminado el roadmap ni integrar ramas por iniciativa propia.
