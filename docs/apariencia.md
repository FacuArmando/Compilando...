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
