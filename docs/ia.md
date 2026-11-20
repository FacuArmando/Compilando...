# Respuestas con Gemini

La consulta se inicia desde «Consultar IA» dentro de una pregunta. Cualquier usuario con sesión válida puede pedirla, incluso cuando ya existen respuestas humanas. Es una acción explícita; publicar una pregunta no llama a Gemini.

## Configuración local

1. Crear una clave en Google AI Studio y usar un proyecto del nivel **Free**, sin habilitar facturación, para la modalidad gratuita. Las cuotas y la disponibilidad dependen de Google y del proyecto.
2. Guardar la clave únicamente en `.env`, que está excluido de Git:

   ```dotenv
   GEMINI_API_KEY=clave_personal
   ```

3. Aplicar las migraciones y reiniciar Flask:

   ```bash
   uv run flask --app compilando:create_app db upgrade
   uv run flask --app compilando:create_app run --host 127.0.0.1 --port 5051
   ```

No hace falta instalar otro SDK: el adaptador usa HTTPS y JSON de la biblioteca estándar de Python. El modelo configurado en `config.py` es `gemini-3.5-flash-lite`, con acceso gratuito documentado al implementar esta entrega. No hay cambio automático a un proveedor o modelo de pago.

La clave se lee en el servidor, se transmite en la cabecera `x-goog-api-key` y nunca se incorpora al HTML, JavaScript, la URL o los mensajes de error. No compartir `.env` ni pegar claves en capturas. Si una clave se expone, revocarla en Google AI Studio y reemplazarla localmente.

## Recorrido del usuario

- Abrir una pregunta e iniciar sesión.
- Desplegar «Consultar IA» y confirmar el envío de la pregunta a Gemini.
- Opcionalmente incluir sus archivos adjuntos; esa opción empieza desmarcada.
- Pedir la respuesta. Mientras espera puede continuar escribiendo su respuesta humana.
- El resultado se agrega al listado sin recargar ni borrar ese borrador. Queda identificado con IA, proveedor y modelo. Los bloques de código se distinguen visualmente; no se interpreta HTML del modelo.
- Si falla la conexión, la cuota o la configuración, se muestra un mensaje y no se publica una respuesta vacía. Una sesión vencida muestra el enlace de ingreso.

Sin JavaScript funciona como un formulario POST tradicional y vuelve a la pregunta tras terminar.

## Contexto y límites

Solo se envían el título, el cuerpo de la pregunta y, si se seleccionan, los nombres y contenidos de sus adjuntos. No se agregan datos de cuenta, correos, contraseñas, cookies, historial de navegación ni otras preguntas.

El usuario ve que las consultas del nivel gratuito pueden usarse para mejorar productos de Google. Se usa `generateContent` para una consulta independiente, sin crear conversaciones, subir archivos a la API de Files ni enviar un historial de interacciones. Esto no sustituye las condiciones de tratamiento de datos del nivel gratuito.

La pregunta y los archivos juntos deben ocupar como máximo **48 KiB** de contexto JSON UTF-8. Este límite es distinto al de subir adjuntos: no se recortan archivos silenciosamente. Si el ejemplo es demasiado grande, se pide reducirlo o consultar sin adjuntos. El código se trata como texto: no se compila, ejecuta ni se habilitan herramientas, navegación o lectura de archivos externos.

Por cada ventana de 15 minutos se admiten hasta 5 intentos por cuenta, 20 por IP y 30 para toda la aplicación. Se comparten entre procesos mediante los contadores persistentes existentes; los fallos también cuentan. La cuota de Google puede ser menor y se informa por separado. La respuesta se limita a 1.800 tokens; el transporte espera hasta 40 segundos de inactividad de red y limita la lectura a 128 KiB. No se hacen reintentos automáticos al proveedor.

## Persistencia y concurrencia

La primera versión conserva **una respuesta de IA compartida por pregunta**. Si ya existe, devuelve la misma sin consumir otra consulta. Para volver a generar o elegir varios proveedores se deberá definir otro caso de uso.

`solicitudes_ia` usa la pregunta como clave única. Registra al solicitante, un token de reserva y un vencimiento de 90 segundos. La reserva se confirma antes de llamar a Gemini, sin mantener una transacción abierta durante la espera. Dos solicitudes simultáneas no generan dos respuestas. Una reserva abandonada se puede reclamar después de vencer; un resultado de una reserva anterior no puede sobrescribir la nueva.

La publicación de la respuesta y la finalización de la solicitud se confirman en la misma transacción. `Respuesta.usuario_id` queda vacío para la IA; `solicitudes_ia.solicitante_id` registra quién la pidió. Las respuestas humanas conservan su autor. Nadie puede editar el texto generado como si lo hubiera escrito, incluso en filas IA anteriores que tuvieran un usuario asociado. El autor de la pregunta puede aceptarlo mediante la función existente.

La migración `a4e18c902b71` crea `solicitudes_ia`, agrega `proveedor_ia` y permite `usuario_id` vacío en respuestas de IA. Al revertir, conserva las respuestas y les asocia el solicitante, como exigía el esquema previo; las marcas IA y modelo se mantienen.

## Organización y pruebas

- `modules/ai/providers.py`: contrato `ProveedorIA`, adaptador Gemini y errores seguros.
- `modules/ai/services.py`: contexto, límites, reserva, publicación y reutilización.
- `modules/ai/routes.py`: POST autenticado con CSRF; JSON para la interfaz o redirección para HTML.
- `templates/answers/_list.html`: listado compartido por la página y la respuesta del POST.
- `tests/test_ai.py`: autenticación y CSRF, privacidad del contexto, errores, cuotas, simultaneidad, persistencia, migración y contrato HTTP del proveedor. Las pruebas automáticas sustituyen Gemini para no consumir cuota ni usar claves reales.

Referencias oficiales: [inicio y REST](https://aistudio.google.com/docs/get-started), [generación de texto](https://aistudio.google.com/docs/text-generation), [precios y nivel gratuito](https://aistudio.google.com/docs/pricing#gemini-3.5-flash-lite), [contrato generateContent](https://aistudio.google.com/api-reference/generate-content/generate-content) y [seguridad de claves](https://aistudio.google.com/docs/api-key).
