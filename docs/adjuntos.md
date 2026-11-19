# Archivos adjuntos a preguntas

La tarea #20 amplía el formulario de publicación existente. No agrega otro formulario ni cambia los requisitos de título, descripción, categoría o etiquetas. Publicar sin archivos sigue funcionando.

## Recorrido

1. El usuario inicia sesión y abre el formulario, desde el inicio o su página propia.
2. Elige uno o varios archivos desde su equipo, o los arrastra a la zona de adjuntos.
3. Cada tarjeta muestra nombre y tamaño; el botón de quitar permite revisar la selección.
4. Los archivos se envían al presionar «Publicar pregunta», junto con los campos y CSRF.
5. En la pregunta publicada, cualquier lector puede abrir el código como texto o descargar los bytes originales. Se mantienen saltos de línea, tabulaciones y comentarios; no se exige código compilable.

El selector nativo sigue disponible si JavaScript está deshabilitado. Agregar archivos en varias selecciones, arrastrarlos y quitarlos individualmente requiere JavaScript. Si el servidor rechaza el envío, conserva los campos escritos y pide seleccionar los archivos nuevamente: el navegador no permite restaurar una selección local desde el servidor.

## Límites iniciales

- Hasta 10 archivos por pregunta, opcionales.
- Hasta 1 MB por archivo y 5 MB entre todos (1 MB = 1.048.576 bytes).
- Extensiones iniciales: `.java`, `.py`, `.js`, `.jsx` y `.txt`.
- Contenido de texto UTF-8, sin bytes de control binarios; archivos vacíos rechazados.
- Nombre de hasta 120 caracteres, sin controles ni caracteres invisibles que puedan disfrazarlo. Se descartan los directorios enviados como parte del nombre. Se conservan nombres con acentos y las extensiones permitidas en mayúsculas.

## Validación de archivos (#21)

El navegador revisa cantidad, tamaños, nombre, extensión y contenido antes de agregar una selección. Lee los archivos localmente: no los envía durante esa revisión. Si alguno no cumple, rechaza esa selección completa y conserva los archivos válidos que ya estaban en las tarjetas. Los errores indican qué corregir y los límites de tamaño exactos. También informa si no pudo leer un archivo y rechaza carpetas, incluso cuando se arrastran junto con archivos.

Mientras revisa contenido, se impide publicar o reiniciar el formulario para no enviar una selección incompleta. Al terminar se puede corregir la selección, quitar adjuntos o publicar normalmente.

El servidor repite los controles de forma independiente, incluso sin JavaScript. El tipo MIME enviado por el cliente no decide qué se acepta: renombrar un binario como `.java` no evita la validación de texto UTF-8 y controles binarios. Se rechazan también los archivos que contienen solo una marca de codificación UTF-8 (BOM), los que llegan con contenido pero sin nombre y los enviados en un campo de archivos distinto al selector previsto. Un selector nativo sin archivos sigue siendo válido.

El límite del nombre cuenta caracteres Unicode, no bytes; un acento o un emoji no cuenta como varios caracteres por su codificación. El contenido puede incluir acentos, comentarios, tabulaciones, saltos de línea de Windows o Unix y una marca BOM inicial. La descarga conserva todos los bytes originales. La validación no analiza si el programa compila o resuelve el problema: el código incompleto sigue permitido.

Los valores están centralizados en `compilando/config.py`: `QUESTION_ATTACHMENT_MAX_FILES`, `QUESTION_ATTACHMENT_MAX_BYTES`, `QUESTION_ATTACHMENT_TOTAL_BYTES` y `QUESTION_ATTACHMENT_EXTENSIONS`. La petición completa tiene un margen adicional para los campos y el envoltorio multipart, un límite de partes y otro para los campos de texto. Una carga excesiva recibe un aviso HTTP 413.

## Persistencia y acceso

La migración `86c41e902ab7` agrega `adjuntos_pregunta`, relacionada con `preguntas`. Guarda identificador aleatorio, nombre original, tamaño y orden. No modifica preguntas anteriores.

Los bytes se guardan en `instance/question-attachments/`, fuera de `static` y excluidos de Git por la regla existente de `instance/`. La carpeta se puede cambiar mediante `QUESTION_UPLOAD_FOLDER` en la configuración. Los nombres internos son aleatorios y sin extensión; no se usan rutas recibidas del usuario. Los respaldos y despliegues deben conservar tanto la base como esta carpeta.

Antes de guardar se validan todos los archivos. La publicación confirma la pregunta y sus metadatos en una misma transacción; si falla la escritura o la transacción, se revierten los cambios y se eliminan los archivos escritos por ese intento. Una interrupción abrupta del proceso podría dejar archivos huérfanos; una tarea de conciliación y el borrado de adjuntos al eliminar preguntas quedan fuera del alcance actual, que no incluye eliminar preguntas.

Solo una sesión válida puede subir archivos y el POST conserva CSRF. Lectura y descarga son públicas como las preguntas: la interfaz avisa que se deben elegir únicamente archivos que se quieran compartir. El identificador de un adjunto debe corresponder a la pregunta de la URL. El visor escapa el texto recibido y la descarga usa `Content-Disposition: attachment`, `application/octet-stream` y `nosniff`; nunca se ejecuta ni compila código.

## Aplicar y comprobar

Cada integrante debe aplicar la migración en su copia, antes de probar adjuntos:

```bash
uv run --locked flask --app compilando:create_app db upgrade
uv run --locked pytest tests/test_question_attachments.py
```

Las pruebas usan bases y carpetas temporales. Cubren publicación opcional y múltiple, originales intactos, mismo nombre sin sobrescribir, vista pública escapada, descarga, pertenencia a la pregunta, sesión/CSRF, límites exactos y excesos, fallos de escritura y transacción, y migración reversible conservando preguntas previas.

Para #21 incluyen cargas manipuladas con MIME falso, binarios renombrados, UTF-8 inválido, archivo sin nombre, BOM vacío, nombres invisibles, nombres Unicode en el límite, todas las extensiones admitidas, configuración de tamaños y límites de partes y campos multipart. Se verifica que un archivo inválido después de uno válido no deje ninguna publicación ni archivo parcial. Esta tarea no agrega otra migración: usa la tabla creada por #20.
