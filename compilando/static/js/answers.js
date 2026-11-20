document.addEventListener("DOMContentLoaded", () => {
    const campoCuerpo = document.getElementById("cuerpo");

    const responder = document.querySelector('.question-reply-link');
    if (responder && campoCuerpo) {
        responder.addEventListener("click", () => campoCuerpo.focus({ preventScroll: true }));
    }

    const consulta = document.getElementById("form-consulta-ia");
    if (consulta && window.fetch) {
        const boton = consulta.querySelector('button[type="submit"]');
        const estado = consulta.querySelector(".ai-status");
        let enviando = false;
        consulta.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (enviando || !consulta.reportValidity()) return;
            enviando = true;
            boton.disabled = true;
            boton.textContent = "Gemini está preparando la respuesta…";
            consulta.setAttribute("aria-busy", "true");
            estado.replaceChildren();
            estado.textContent = "Podés seguir escribiendo tu respuesta mientras esperás.";
            let completada = false;
            const controlador = new AbortController();
            const esperaMaxima = setTimeout(() => controlador.abort(), 65000);
            try {
                const response = await fetch(consulta.action, {
                    method: "POST",
                    credentials: "same-origin",
                    headers: { Accept: "application/json" },
                    body: new FormData(consulta),
                    signal: controlador.signal,
                });
                if (!response.headers.get("content-type")?.includes("application/json")) {
                    throw new Error("El formulario pudo haber vencido. Recargá la pregunta para comprobar el resultado.");
                }
                const data = await response.json();
                if (!response.ok) {
                    estado.textContent = data.error || "No se pudo consultar IA. Volvé a intentarlo.";
                    if (data.login_url) {
                        const link = document.createElement("a");
                        const destino = new URL(data.login_url, window.location.origin);
                        if (destino.origin === window.location.origin) {
                            link.href = destino.href;
                            link.textContent = " Iniciar sesión";
                            estado.append(link);
                        }
                    }
                    return;
                }
                // HTML generado por nuestras plantillas con autoescape; nunca HTML del modelo.
                const fragmento = new DOMParser().parseFromString(data.html, "text/html");
                const id = `respuesta-${data.respuesta_id}`;
                const nuevaRespuesta = fragmento.getElementById(id);
                if (!nuevaRespuesta) throw new Error("Falta la respuesta generada.");
                if (!document.getElementById(id)) {
                    document.querySelector("#answer-list .question-no-answers")?.remove();
                    document.getElementById("answer-list").append(nuevaRespuesta);
                }
                document.querySelectorAll("[data-answer-count]").forEach((item) => {
                    item.textContent = `${data.cantidad} ${data.cantidad === 1 ? "respuesta" : "respuestas"}`;
                });
                estado.textContent = "La respuesta de Gemini está publicada. ";
                const enlace = document.createElement("a");
                enlace.href = `#respuesta-${data.respuesta_id}`;
                enlace.textContent = "Ver respuesta";
                estado.append(enlace);
                completada = true;
            } catch (error) {
                estado.textContent = "No pudimos confirmar el resultado. Recargá la pregunta antes de volver a intentar; tu texto sigue en este formulario.";
            } finally {
                clearTimeout(esperaMaxima);
                consulta.removeAttribute("aria-busy");
                boton.disabled = completada;
                boton.textContent = completada ? "Respuesta de IA publicada" : "Volver a intentar";
                enviando = completada;
            }
        });
    }

    // Mostrar formulario de edición en la respuesta propia
    document.addEventListener("click", (event) => {
        const boton = event.target.closest(".btn-editar-respuesta");
        if (boton) {
            const id = boton.getAttribute("data-respuesta-id");
            const vista = document.getElementById(`contenido-respuesta-${id}`);
            const formEdit = document.getElementById(`form-editar-respuesta-${id}`);
            if (vista && formEdit) {
                vista.classList.add("hidden");
                formEdit.classList.remove("hidden");
                formEdit.querySelector("textarea")?.focus();
            }
        }
    });

    // Cancelar edición y volver a mostrar el texto original
    document.addEventListener("click", (event) => {
        const boton = event.target.closest(".btn-cancelar-edicion");
        if (boton) {
            const id = boton.getAttribute("data-respuesta-id");
            const vista = document.getElementById(`contenido-respuesta-${id}`);
            const formEdit = document.getElementById(`form-editar-respuesta-${id}`);
            if (vista && formEdit) {
                formEdit.classList.add("hidden");
                vista.classList.remove("hidden");
                vista.querySelector(".btn-editar-respuesta")?.focus();
            }
        }
    });
});
