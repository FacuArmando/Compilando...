document.addEventListener("DOMContentLoaded", () => {
    const btnUsuario = document.getElementById("btn-modo-usuario");
    const btnIa = document.getElementById("btn-modo-ia");
    const formUsuario = document.getElementById("form-respuesta-usuario");
    const avisoIa = document.getElementById("mensaje-ia-proximamente");
    const campoCuerpo = document.getElementById("cuerpo");

    if (btnUsuario && btnIa && formUsuario && avisoIa) {
        btnUsuario.addEventListener("click", () => {
            avisoIa.classList.add("hidden");
            formUsuario.classList.remove("hidden");
            if (campoCuerpo) {
                campoCuerpo.focus();
            }
        });

        btnIa.addEventListener("click", () => {
            formUsuario.classList.add("hidden");
            avisoIa.classList.remove("hidden");
        });
    }

    // Mostrar formulario de edición en la respuesta propia
    document.querySelectorAll(".btn-editar-respuesta").forEach((boton) => {
        boton.addEventListener("click", () => {
            const id = boton.getAttribute("data-respuesta-id");
            const vista = document.getElementById(`contenido-respuesta-${id}`);
            const formEdit = document.getElementById(`form-editar-respuesta-${id}`);
            if (vista && formEdit) {
                vista.classList.add("hidden");
                formEdit.classList.remove("hidden");
            }
        });
    });

    // Cancelar edición y volver a mostrar el texto original
    document.querySelectorAll(".btn-cancelar-edicion").forEach((boton) => {
        boton.addEventListener("click", () => {
            const id = boton.getAttribute("data-respuesta-id");
            const vista = document.getElementById(`contenido-respuesta-${id}`);
            const formEdit = document.getElementById(`form-editar-respuesta-${id}`);
            if (vista && formEdit) {
                formEdit.classList.add("hidden");
                vista.classList.remove("hidden");
            }
        });
    });
});
