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
