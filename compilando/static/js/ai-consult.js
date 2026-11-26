/* Una consulta explícita; la espera no reemplaza el borrador ni mueve el foco. */
(() => {
  "use strict";
  const form = document.getElementById("form-consulta-ia");
  if (!form || !window.fetch || !window.I18n || !window.AbortController) return;
  const button = form.querySelector('button[type="submit"]');
  const label = form.querySelector(".ai-submit-label");
  const status = form.querySelector(".ai-status");
  const loading = form.querySelector(".ai-loading");
  const hint = form.querySelector(".ai-wait-hint");
  const settings = form.querySelector(".ai-settings");
  let busy = false;

  const state = (value) => {
    form.dataset.aiState = value;
    loading.hidden = value !== "loading";
    hint.hidden = value !== "loading";
    settings.disabled = value === "loading" || value === "success";
    button.disabled = value === "loading" || value === "success";
    if (value === "loading") form.setAttribute("aria-busy", "true");
    else form.removeAttribute("aria-busy");
    window.I18n.setText(label, value === "loading" ? "Generando…"
      : value === "success" ? "Respuesta de IA publicada" : "Volver a intentar");
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy || !form.reportValidity()) return;
    // Capturar confirmación y adjuntos antes de deshabilitar las opciones.
    const payload = new FormData(form);
    busy = true;
    state("loading");
    window.I18n.setText(status, "Gemini está preparando la respuesta…");
    let completed = false;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 65000);
    try {
      const response = await fetch(form.action, {
        method: "POST", credentials: "same-origin",
        headers: { Accept: "application/json" }, body: payload, signal: controller.signal,
      });
      if (!response.headers.get("content-type")?.includes("application/json")) {
        throw new Error("unexpected response");
      }
      const data = await response.json();
      if (!response.ok) {
        window.I18n.setText(status, data.error || "No se pudo consultar IA. Volvé a intentarlo.");
        if (data.login_url) {
          const destination = new URL(data.login_url, window.location.origin);
          if (destination.origin === window.location.origin) {
            const link = document.createElement("a");
            link.href = destination.href;
            window.I18n.setText(link, "Iniciar sesión");
            status.append(" ", link);
          }
        }
        return;
      }
      // Fragmento de nuestras plantillas con autoescape, nunca HTML crudo del modelo.
      const fragment = new DOMParser().parseFromString(data.html, "text/html");
      const id = `respuesta-${data.respuesta_id}`;
      const answer = fragment.getElementById(id);
      if (!answer) throw new Error("missing answer");
      if (!document.getElementById(id)) {
        document.querySelector("#answer-list .question-no-answers")?.remove();
        answer.classList.add("answer-ai-arrived");
        document.getElementById("answer-list").append(answer);
      }
      document.querySelectorAll("[data-answer-count]").forEach((element) => {
        window.I18n.setText(element, data.cantidad === 1 ? "{count} respuesta" : "{count} respuestas",
          { count: data.cantidad });
      });
      window.I18n.setText(status, "La respuesta de Gemini está publicada.");
      const link = document.createElement("a");
      link.href = `#respuesta-${data.respuesta_id}`;
      window.I18n.setText(link, "Ver respuesta");
      status.append(" ", link);
      completed = true;
    } catch {
      window.I18n.setText(status, "No pudimos confirmar el resultado. Recargá la pregunta antes de volver a intentar; tu texto sigue en este formulario.");
    } finally {
      clearTimeout(timeout);
      state(completed ? "success" : "error");
      busy = completed;
    }
  });
})();
