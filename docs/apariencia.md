# Apariencia clara y oscura

El switch de sol y luna está en la cabecera de la comunidad y en la esquina
superior derecha de las pantallas de acceso y publicación independiente.
Se puede usar con el mouse, Enter o la barra espaciadora.

La primera visita sigue la preferencia del sistema. Al elegir un tema, se guarda
en el navegador con la clave `compilando-theme`; la elección se conserva entre
páginas, recargas y pestañas del mismo sitio. No se guarda en la cuenta ni en la
base de datos. Si el almacenamiento está bloqueado, el control sigue funcionando
durante la página actual. Sin JavaScript, queda disponible el diseño claro.

El cambio de tema revela una onda circular desde el switch durante 1,4 segundos
mediante View Transitions. Los navegadores sin esa API usan una transición de
colores. Si el sistema solicita reducir el movimiento, el cambio es inmediato.
Cambiar la apariencia conserva el contenido de los formularios.

Los colores oscuros y la animación están en `compilando/static/css/theme.css`.
Los estilos de cada pantalla usan variables `--theme-*` con sus colores claros
originales como alternativa. `compilando/static/js/theme.js` aplica la preferencia
antes de cargar los estilos para evitar un destello claro al navegar.

Esta función no necesita dependencias nuevas ni migraciones de base de datos.

## Marca de Compilando

La cabecera de la comunidad y las pantallas de login y registro comparten el logo
con el ajolote. La marca enlaza al inicio y conserva su nombre al cambiar el idioma.
En celular se ajusta al espacio disponible, sin superponerse con los switches.

El archivo original está en `compilando/static/img/brand/compilando-original.png`.
El parcial `_brand.html` usa filtros SVG para separar su fondo grafito al mostrarlo,
conservar el color de la mascota y adaptar las letras al contraste de cada tema.
El recorte y los estilos están centralizados en ese parcial y en `css/brand.css`;
no se modifican los píxeles del original ni se usan servicios externos para mostrarlo.

## Pie de página de la comunidad

El inicio, las preguntas, el visor de adjuntos y «Mi cuenta» comparten un footer
con la marca en gran formato, navegación a la derecha y una franja inferior con
el repositorio del proyecto y el enlace «Volver arriba». Los accesos muestran
«Mi cuenta» si hay sesión, o «Ingresar» y «Crear cuenta» para visitantes.
En celular, el contenido se organiza en una sola columna.

El footer queda después del contenido y llega al borde inferior en páginas
cortas; no es fijo ni tapa formularios. Login y registro conservan sus pantallas
independientes. La marca mantiene sus proporciones y el color original del ajolote,
con letras que se adaptan al tema claro u oscuro. Los textos se traducen con ES / EN.

La plantilla `community/base.html` incluye `community/_footer.html` fuera del
contenido principal. `footer.css` define la presentación y `footer.js` agrega una
entrada suave al llegar al pie y el regreso al inicio con desplazamiento suave.
Ambos efectos respetan el movimiento reducido. Sin JavaScript, todo el contenido
y los enlaces siguen visibles y disponibles. No requiere cambios de base de datos.

## Castellano e inglés

El control ES / EN está junto al switch de apariencia. Cambia el idioma de la
interfaz sin recargar la página: navegación, formularios, mensajes de error,
fechas y controles que se cargan después, como el formulario de preguntas y las
respuestas de IA. Conserva el texto escrito y los archivos seleccionados.

La elección queda en la cookie `compilando-language` durante un año. El servidor
también la usa al abrir otra página, por lo que el idioma permanece al navegar.
El castellano es el valor inicial; los valores desconocidos se ignoran. Esta
cookie es independiente de la sesión y no contiene datos personales.

Al cambiar de idioma, las etiquetas visibles se transforman brevemente en
caracteres aleatorios hasta revelar el texto elegido. La animación dura alrededor
de un segundo, se cancela al ocultar la pestaña y respeta la preferencia de
movimiento reducido. El control admite mouse, Enter y barra espaciadora.

Se traducen solo las etiquetas marcadas expresamente. Nombres de usuario,
preguntas, categorías, etiquetas, respuestas humanas o de IA y archivos de código
mantienen su contenido original. Cambiar el idioma no vuelve a consultar a Gemini.

Las traducciones están en `compilando/translations/en.json`; `compilando/i18n.py`
las aplica en las plantillas y publica el catálogo de interfaz, sin incluir datos
de usuarios. `language.js` actualiza el texto y anima las etiquetas; `language.css`
define el switch y el efecto. No requiere dependencias ni migraciones nuevas.

## Código animado en las pantallas de acceso

El panel izquierdo del login y del registro comparte una escena de Java: escribe
fragmentos de interfaces, herencia y colecciones, transforma sus primeros bytes
UTF-8 en binario, los borra y elige otro fragmento sin repetir el anterior.
El editor tiene colores de sintaxis y un movimiento flotante suave.

El botón de pausa permite detener o reanudar la escena. La preferencia del sistema
de movimiento reducido muestra código estático; la animación también se detiene
cuando la pestaña está oculta. En pantallas de hasta 760 px se oculta la escena
para mantener el formulario cerca del comienzo de la página. Sin JavaScript
permanece un ejemplo estático de Java.

La escena usa `auth-code.css`, `auth-code.js` y el parcial `auth/_visual.html`.
Solo trabaja con fragmentos locales de texto, sin leer campos del formulario,
ejecutar Java, acceder a la base de datos ni consultar servicios externos.
