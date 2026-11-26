document.addEventListener("DOMContentLoaded", () => {
    // Delegar el envío también cubre las respuestas de IA agregadas después de cargar.
    document.addEventListener("submit", async (event) => {
        const form = event.target;
        if (!form.matches(".answer-feedback-form") || !window.fetch || !window.I18n) return;
        const boton = event.submitter || form.querySelector('button[name="utilidad"]');
        if (!boton) return;
        event.preventDefault();
        if (form.dataset.feedbackBusy) return;

        const panel = form.closest(".answer-feedback");
        const estado = panel.querySelector(".answer-feedback-status");
        const botones = [...form.querySelectorAll('button[name="utilidad"]')];
        const datos = new FormData(form);
        datos.set("utilidad", boton.value);
        const teniaFoco = document.activeElement === boton;
        form.dataset.feedbackBusy = "true";
        form.setAttribute("aria-busy", "true");
        botones.forEach((item) => {
            item.disabled = true;
            item.removeAttribute("data-feedback-effect");
        });
        estado.classList.remove("is-error");
        window.I18n.setText(estado, "Guardando tu opinión…");
        const controlador = new AbortController();
        const limite = setTimeout(() => controlador.abort(), 15000);
        try {
            const response = await fetch(form.action, {
                method: "POST",
                credentials: "same-origin",
                headers: { Accept: "application/json" },
                body: datos,
                signal: controlador.signal,
            });
            if (!response.headers.get("content-type")?.includes("application/json")) {
                throw new Error("Respuesta inesperada");
            }
            const data = await response.json();
            if (!response.ok) {
                estado.classList.add("is-error");
                window.I18n.setText(estado, data.error || "No pudimos confirmar tu evaluación. Recargá la pregunta para comprobarla.");
                return;
            }
            if (String(data.respuesta_id) !== form.dataset.respuestaId
                || ![true, false, null].includes(data.utilidad)
                || !Number.isInteger(data.cantidad_utiles) || data.cantidad_utiles < 0
                || typeof data.mensaje !== "string" || !data.mensaje) {
                throw new Error("Evaluación inesperada");
            }
            botones.forEach((item) => {
                const elegido = data.utilidad === (item.dataset.feedbackChoice === "si");
                item.value = elegido ? "retirar" : item.dataset.feedbackChoice;
                item.setAttribute("aria-pressed", String(elegido));
                window.I18n.setAttribute(item, "title", elegido ? "Retirar mi evaluación"
                    : item.dataset.feedbackChoice === "si" ? "Me ayudó" : "No me ayudó");
                if (elegido) item.setAttribute("data-feedback-effect", item.dataset.feedbackChoice);
            });
            let conteo = panel.querySelector(".answer-feedback-count");
            if (data.cantidad_utiles > 0) {
                if (!conteo) {
                    conteo = document.createElement("p");
                    conteo.className = "answer-feedback-count";
                    panel.append(conteo);
                }
                window.I18n.setText(conteo, data.cantidad_utiles === 1
                    ? "A {count} persona le ayudó" : "A {count} personas les ayudó",
                    { count: data.cantidad_utiles });
            } else conteo?.remove();
            window.I18n.setText(estado, data.mensaje);
        } catch {
            estado.classList.add("is-error");
            window.I18n.setText(estado, "No pudimos confirmar tu evaluación. Recargá la pregunta para comprobarla.");
        } finally {
            clearTimeout(limite);
            delete form.dataset.feedbackBusy;
            form.removeAttribute("aria-busy");
            botones.forEach((item) => { item.disabled = false; });
            if (teniaFoco && (document.activeElement === document.body || form.contains(document.activeElement))) {
                boton.focus({ preventScroll: true });
            }
        }
    });

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
            window.I18n.setText(boton, "Gemini está preparando la respuesta…");
            consulta.setAttribute("aria-busy", "true");
            estado.replaceChildren();
            window.I18n.setText(estado, "Podés seguir escribiendo tu respuesta mientras esperás.");
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
                    window.I18n.setText(estado, data.error || "No se pudo consultar IA. Volvé a intentarlo.");
                    if (data.login_url) {
                        const link = document.createElement("a");
                        const destino = new URL(data.login_url, window.location.origin);
                        if (destino.origin === window.location.origin) {
                            link.href = destino.href;
                            window.I18n.setText(link, "Iniciar sesión");
                            estado.append(" ", link);
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
                    window.I18n.setText(item, data.cantidad === 1 ? "{count} respuesta" : "{count} respuestas", { count: data.cantidad });
                });
                window.I18n.setText(estado, "La respuesta de Gemini está publicada.");
                const enlace = document.createElement("a");
                enlace.href = `#respuesta-${data.respuesta_id}`;
                window.I18n.setText(enlace, "Ver respuesta");
                estado.append(" ", enlace);
                completada = true;
            } catch (error) {
                window.I18n.setText(estado, "No pudimos confirmar el resultado. Recargá la pregunta antes de volver a intentar; tu texto sigue en este formulario.");
            } finally {
                clearTimeout(esperaMaxima);
                consulta.removeAttribute("aria-busy");
                boton.disabled = completada;
                window.I18n.setText(boton, completada ? "Respuesta de IA publicada" : "Volver a intentar");
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

// Modal de confirmación para eliminar pregunta
const btnAbrirEliminarPregunta = document.getElementById("btn-abrir-eliminar-pregunta");
const dialogEliminarPregunta = document.getElementById("dialog-eliminar-pregunta");
const btnCancelarEliminarPregunta = document.getElementById("btn-cancelar-eliminar-pregunta");

if (btnAbrirEliminarPregunta && dialogEliminarPregunta && btnCancelarEliminarPregunta) {
  btnAbrirEliminarPregunta.addEventListener("click", () => dialogEliminarPregunta.showModal());
  btnCancelarEliminarPregunta.addEventListener("click", () => dialogEliminarPregunta.close());
  dialogEliminarPregunta.addEventListener("click", (event) => {
    if (event.target === dialogEliminarPregunta) dialogEliminarPregunta.close();
  });
}

// Modal de confirmación para eliminar respuestas propias
document.querySelectorAll(".btn-abrir-eliminar-respuesta").forEach((btn) => {
  btn.addEventListener("click", () => {
    const dialog = document.getElementById(`dialog-eliminar-respuesta-${btn.dataset.respuestaId}`);
    if (dialog) dialog.showModal();
  });
});

document.querySelectorAll(".btn-cancelar-eliminar-respuesta").forEach((btn) => {
  btn.addEventListener("click", () => {
    const dialog = document.getElementById(`dialog-eliminar-respuesta-${btn.dataset.respuestaId}`);
    if (dialog) dialog.close();
  });
});

document.querySelectorAll("dialog[id^='dialog-eliminar-respuesta-']").forEach((dialog) => {
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
});
