# Paginación del listado de preguntas

La primera versión muestra **20 preguntas por página**. Debajo del listado, antes del footer, aparecen «Anterior», «Siguiente», la página actual, sus vecinas y los extremos. Los puntos suspensivos evitan mostrar cientos de enlaces. Si hay una sola página, se muestra únicamente el rango de resultados.

La URL usa `page`: por ejemplo, `/?page=2#preguntas`. Al cambiar de página se mantienen la búsqueda y la categoría. Una búsqueda nueva vuelve a la primera página. Las páginas inválidas o fuera del listado redirigen a la primera conservando los filtros; un listado vacío muestra su mensaje habitual.

El orden es fecha descendente y, para publicaciones del mismo día, ID descendente. Se conserva la prioridad de preguntas con respuestas aceptadas cuando se combinan búsqueda y categoría; en ese caso, la pantalla indica «Aceptadas primero».

## Consulta y migración

La base devuelve solo las 20 preguntas solicitadas. El listado trae sus autores, categorías y etiquetas sin una consulta adicional por tarjeta. Cuenta las respuestas de esas preguntas mediante una consulta agrupada: no carga los cuerpos de todas las respuestas para mostrar un número.

La revisión `d29f08e731c4` agrega índices para el orden por fecha e ID, el filtro por categoría y los conteos/estados de respuestas. No cambia publicaciones existentes. Después de actualizar el proyecto, ejecutar:

```bash
uv run flask --app compilando:create_app db upgrade
```

## Comprobaciones y alcance

Las pruebas cubren límites entre páginas, filtros, orden estable, URLs inválidas, visitantes y usuarios conectados, ambos idiomas y conteos sin cargar respuestas completas. Recorren 300 preguntas en una base temporal y comprueban que cada publicación aparezca una vez. También verifican la aplicación y reversión de los índices conservando publicaciones.

Esta versión usa `LIMIT/OFFSET` y un conteo total para ofrecer páginas numeradas. Limita lo enviado al navegador, pero los saltos a páginas muy lejanas y las búsquedas por texto pueden seguir siendo costosos con millones de registros. Antes de afirmar que soporta ese volumen, hay que medir consultas con datos representativos; si hace falta, evaluar paginación por cursor y un índice de búsqueda de texto. Las pruebas con 300 preguntas verifican comportamiento, no capacidad para diez millones.
