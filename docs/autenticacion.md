# Autenticación con sesiones en la base

Decisión del 13 de noviembre de 2026: usar sesiones del servidor para la aplicación
Flask con páginas Jinja. Este mecanismo implementa la entidad `Sesion` del UML,
permite revocar el acceso desde la base y utiliza las dependencias existentes.

## Recorrido y almacenamiento

El login busca el correo normalizado mediante una consulta parametrizada de
SQLAlchemy y comprueba el hash de contraseña con Werkzeug. Una cuenta inexistente
también ejecuta una comprobación de hash para reducir diferencias de tiempo. Los
errores de credenciales tienen el mismo mensaje y estado HTTP.

Cada ingreso válido genera un identificador aleatorio con 256 bits de entropía.
La cookie firmada de Flask contiene ese identificador; la tabla `sesiones` guarda
únicamente su SHA-256, el usuario, inicio, último acceso, vencimiento y estado.
Ni la cookie ni el HTML contienen contraseñas o sus hashes. La firma de la cookie
no cifra su contenido: debe tratarse como una credencial y protegerse con HTTPS.

Cada solicitud dinámica con una sesión comprueba su estado y usuario en la base;
`/health` permanece independiente de la base para comprobar el proceso web.
Vence a las 8 horas o tras 30 minutos de inactividad, lo que ocurra primero. Un
nuevo login rota la sesión del navegador e invalida la anterior. Logout requiere
POST con CSRF, revoca la sesión en la base y borra el estado del navegador.

## Controles

- CSRF activo para registro, login y logout. Al ingresar se renueva el token CSRF.
- Formularios de autenticación limitados a 16 KiB antes de leer su contenido.
- Límites persistentes por ventanas de 15 minutos: 5 envíos de login por correo,
  30 por IP y 10 registros por IP. Incluyen envíos válidos e inválidos con CSRF
  válido. Las reservas de intentos se actualizan atómicamente en la base; no
  dependen de cookies ni de memoria de un proceso. Un rechazo devuelve 429 y
  `Retry-After`. Las claves de los contadores usan HMAC para no guardar correos
  ni direcciones IP en texto plano.
- Se utiliza la IP de la conexión. No se confía en `X-Forwarded-For` enviado por
  el cliente. Un despliegue detrás de un proxy necesita configurar explícitamente
  cuáles proxies son de confianza y revisar límites compartidos por sus usuarios.
- Cookies `HttpOnly` y `SameSite=Lax`; `Secure` en producción. Sin almacenamiento
  de tokens en JavaScript ni en direcciones URL.
- Escape de datos con Jinja, CSP, protección contra marcos y detección de tipos;
  las respuestas dinámicas llevan `Cache-Control: no-store`.
- Los cuerpos de formularios, contraseñas y tokens no se registran en logs.

## Preparación y límites

Aplicar `uv run flask --app compilando:create_app db upgrade` para agregar las
tablas de sesiones y límites. Las migraciones anteriores se conservan.

En desarrollo se usa HTTP solamente en localhost. Para producción configurar
`APP_ENV=production`, una `SECRET_KEY` aleatoria de al menos 32 caracteres y
`TRUSTED_HOSTS` con los dominios admitidos separados por comas. El arranque valida
estos datos, exige cookies `Secure` y rechaza solicitudes HTTP. El servidor o proxy
debe servir HTTPS; no se debe publicar el servidor de desarrollo ni habilitar
debug. La configuración del proxy debe probarse en el entorno elegido.

Estos controles no sustituyen una revisión del despliegue ni protecciones de
infraestructura contra ataques distribuidos. Registro conserva los mensajes de
duplicados existentes, por lo que permite inferir si un correo o nombre ya está
registrado; cambiar esa experiencia requiere acordar el comportamiento del
registro, incluida la verificación de correo. MFA y recuperación de cuenta quedan
fuera de esta tarea.

Referencias: [seguridad en Flask](https://flask.palletsprojects.com/en/stable/web-security/),
[autenticación en OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
y [sesiones en OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
