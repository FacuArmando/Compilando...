# Compilando... — alcance inicial y plan de implementación

Fecha: 5 de noviembre de 2026. Estado: propuesta inicial basada en la definición del usuario; no es una especificación académica aprobada.

## Producto

Plataforma web de preguntas y respuestas sobre programación, inspirada en Stack Overflow. Los usuarios autenticados pueden publicar preguntas y respuestas humanas. Un botón permite solicitar una respuesta de inteligencia artificial.

La IA responde a una solicitud explícita. No se deriva del requisito que deba responder al publicar, esperar un plazo o intervenir únicamente en preguntas sin respuestas.

## Primera versión útil propuesta

| Función | Resultado verificable |
| --- | --- |
| Iniciar y cerrar sesión | Se reconoce al usuario autenticado; al salir pierde acceso a acciones protegidas. |
| Listar y abrir preguntas | Se puede encontrar una pregunta y ver su contenido y respuestas. |
| Publicar pregunta | La pregunta válida queda guardada y asociada al usuario autenticado. |
| Responder como humano | La respuesta queda asociada a su pregunta y a su autor real. |
| Solicitar respuesta de IA | El botón inicia una solicitud y el resultado se muestra identificado como generado por IA. |

Las cuentas para la primera demostración pueden prepararse como datos de desarrollo. El registro de usuarios se incorporará si forma parte de la consigna o se prioriza para la primera versión pública; no se confunde un login con la creación de cuentas.

Categorías, etiquetas, adjuntos, aceptación de respuestas y administración ya aparecen en el UML. Su orden de implementación queda pendiente de la consigna y del tiempo disponible. Votos, reputación y notificaciones no fueron solicitados y no se añaden al alcance por la referencia a Stack Overflow.

## Historias y criterios de aceptación iniciales

### HU-01 — Autenticación

Como usuario con una cuenta, quiero iniciar sesión para participar con mi identidad.

- Las credenciales válidas permiten entrar.
- Las credenciales incorrectas no autentican al usuario.
- Publicar preguntas, respuestas o solicitudes de IA exige autenticación verificada en el servidor.
- Cerrar sesión impide seguir utilizando las acciones protegidas con esa sesión.
- Las contraseñas se almacenan mediante hash apropiado para contraseñas.

La elección de sesión/JWT y su mecanismo de invalidación se documentarán antes de implementar, tomando en cuenta el taller y el modelo `Sesion`.

### HU-02 — Publicar y consultar preguntas

Como usuario autenticado, quiero publicar una pregunta y verla para recibir ayuda.

- La pregunta requiere título y cuerpo válidos; los límites numéricos siguen pendientes de confirmar.
- Su autor se obtiene de la identidad autenticada, independientemente de lo que envíe el navegador.
- Una pregunta publicada aparece en el listado y tiene una vista de detalle.
- Los datos permanecen disponibles después de reiniciar la aplicación.
- Un envío inválido informa el problema y no crea la pregunta.

### HU-03 — Responder como humano

Como usuario autenticado, quiero responder una pregunta para ayudar a otra persona.

- La pregunta debe existir y el cuerpo de la respuesta no puede estar vacío.
- La respuesta guarda la asociación con su pregunta, su autor y la fecha.
- Otro usuario puede verla al abrir esa pregunta.

### HU-04 — Pedir respuesta de IA

Como usuario autenticado habilitado para esa acción, quiero solicitar una respuesta de IA desde la pregunta.

- La solicitud se inicia con el botón correspondiente.
- La respuesta utiliza el título y cuerpo de la pregunta como contexto inicial. Los adjuntos requieren una definición posterior.
- La interfaz muestra que la solicitud está en curso y luego su resultado o un error comprensible.
- Una respuesta exitosa queda guardada y etiquetada como generada por IA, con identificación de su proveedor/modelo cuando esté disponible.
- Un fallo del proveedor no crea una respuesta vacía ni elimina el contenido de la pregunta.
- Se prueba el manejo de solicitudes repetidas y concurrencia según la política que se acuerde.

Pendientes concretos: quién puede pulsar el botón, si puede hacerlo cuando ya hay respuestas humanas, y cuándo se admite una nueva generación. La restricción «solo si no hay respuestas» no está confirmada.

## Arquitectura inicial propuesta

Una aplicación Flask modular, desplegada como una unidad y con una base de datos. Python y uv siguen la orientación del curso.

| Parte | Responsabilidad |
| --- | --- |
| Pantallas y rutas | Formularios, navegación, solicitudes y presentación de resultados. |
| Servicios | Coordinar publicar, responder y solicitar IA; aplicar permisos y reglas de cada operación. |
| Modelo y acceso a datos | Representar usuarios, preguntas y respuestas, y conservarlos con sus relaciones. |
| Integración de IA | Proveer un contrato común y una estrategia por proveedor que se implemente. |

Se propone `create_app` y módulos de autenticación, preguntas, respuestas e IA. La estructura exacta de carpetas se definirá al iniciar el código. Si se utiliza Repository, tendrá contratos concretos que respondan a las necesidades de los casos de uso.

El patrón Strategy del UML se mantiene como punto de partida para intercambiar proveedores. Inicialmente se puede comprobar su contrato con un sustituto controlado; el hito de IA se completa con al menos un proveedor real configurado y probado. Los restantes dependerán de los requisitos de la materia.

El UML debe reflejar el pedido explícito al gestor y distinguir entre quien solicita la generación y el agente que figura como autor de la respuesta.

Referencias técnicas consultadas: [Application Factories de Flask](https://flask.palletsprojects.com/en/stable/patterns/appfactories/), [gestión de proyectos con uv](https://docs.astral.sh/uv/guides/projects/).

## Orden de trabajo

1. **Preparación compartida:** alcance, historias, decisiones pendientes e instrucciones de colaboración en el repositorio. Cada tarea debe tener un resultado comprobable.
2. **Base ejecutable:** versión de Python elegida, proyecto uv, configuración local de ejemplo, arranque Flask, conexión a base de datos y migración inicial. Dependencias declaradas en `pyproject.toml` y versiones resueltas en `uv.lock`.
3. **Primer hito demostrable:** dos compañeros levantan la aplicación siguiendo el README; uno inicia sesión, publica una pregunta y el otro puede verla. Los datos sobreviven al reinicio. Hay pruebas de los permisos y validaciones de este recorrido.
4. **Respuestas humanas:** el segundo usuario inicia sesión y responde. Se verifica identidad, relación con la pregunta y persistencia.
5. **Botón de IA:** contrato de proveedor, solicitud explícita, estado de espera, respuesta identificada y manejo de fallos. Se incorpora una integración real.
6. **Ampliación y entrega:** funciones exigidas por la consigna, actualización del UML, pruebas de casos límite y despliegue.

## Forma de trabajar en equipo

- Una lista compartida de tareas pequeñas, con responsable y criterio de aceptación.
- Una rama por tarea y revisión de otro integrante antes de integrar los cambios.
- Cambios que mantengan la aplicación ejecutable y comprobaciones automáticas en cada propuesta de integración.
- Acordar juntos el primer recorrido y los contratos antes de repartir funciones en paralelo.
- Registrar decisiones importantes con su motivo y actualizar el diseño cuando cambie el comportamiento.

Una tarea está terminada cuando cumple sus criterios, persiste los datos necesarios, trata los errores pertinentes, pasa las pruebas apropiadas y puede ser revisada y ejecutada por otro integrante.

## Estado

Se preparó esta propuesta y luego se creó una base Flask local con uv, configuración de SQLite, migraciones y módulos reservados. Las funciones del producto todavía no están implementadas. No se realizaron commits ni se subieron cambios al repositorio remoto. Ver el README para el estado ejecutable y los comandos actuales.
