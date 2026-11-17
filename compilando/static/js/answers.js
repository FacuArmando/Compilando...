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
});
