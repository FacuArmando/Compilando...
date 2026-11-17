document.addEventListener("DOMContentLoaded", () => {
    const btnIa = document.getElementById("btn-modo-ia");
    const avisoIa = document.getElementById("mensaje-ia-proximamente");
    const campoCuerpo = document.getElementById("cuerpo");

    const responder = document.querySelector('.question-reply-link');
    if (responder && campoCuerpo) {
        responder.addEventListener("click", () => campoCuerpo.focus({ preventScroll: true }));
    }

    if (btnIa && avisoIa) {
        btnIa.addEventListener("click", () => {
            const mostrar = avisoIa.classList.contains("hidden");
            avisoIa.classList.toggle("hidden", !mostrar);
            btnIa.setAttribute("aria-expanded", String(mostrar));
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
                formEdit.querySelector("textarea")?.focus();
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
                vista.querySelector(".btn-editar-respuesta")?.focus();
            }
        });
    });
});
