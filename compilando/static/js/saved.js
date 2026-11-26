/* Las estrellas del feed/detalle se actualizan solo después de confirmar el servidor. */
(() => {
  "use strict";
  if (!window.fetch || !window.I18n || !window.AbortController) return;
  const busy = new Set();
  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!form.matches(".question-save-form")) return;
    // POST/303 mantiene correctos el relleno de páginas, el orden y los totales al quitar.
    if (form.dataset.savedPage === "true") return;
    event.preventDefault();
    const id = form.dataset.savedQuestion;
    if (!/^\d+$/.test(id) || busy.has(id)) return;
    const button = event.submitter || form.querySelector('button[name="guardada"]');
    const controls = Array.from(document.querySelectorAll(`[data-saved-question="${id}"]`));
    const status = form.closest(".question-save-control").querySelector(".question-save-status");
    const payload = new FormData(form);
    payload.set("guardada", button.value);
    busy.add(id);
    controls.forEach(control => {
      control.querySelector("button").disabled = true;
      control.setAttribute("aria-busy", "true");
      control.querySelector("button").removeAttribute("data-save-effect");
    });
    status.classList.remove("is-error");
    window.I18n.setText(status, "Actualizando Guardadas…");
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(form.action, {
        method: "POST", credentials: "same-origin", headers: { Accept: "application/json" },
        body: payload, signal: controller.signal,
      });
      if (!response.headers.get("content-type")?.includes("application/json")) throw new Error();
      const data = await response.json();
      if (!response.ok) {
        status.classList.add("is-error");
        window.I18n.setText(status, data.error || "No pudimos confirmar el guardado. Volvé a intentar.");
        if (data.login_url) {
          const target = new URL(data.login_url, window.location.origin);
          if (target.origin === window.location.origin) {
            const link = document.createElement("a");
            link.href = target.href;
            window.I18n.setText(link, "Iniciar sesión");
            status.append(" ", link);
          }
        }
        return;
      }
      if (String(data.pregunta_id) !== id || typeof data.guardada !== "boolean") throw new Error();
      controls.forEach(control => {
        const star = control.querySelector("button");
        const key = data.guardada ? "Quitar de Guardadas" : "Guardar pregunta";
        star.value = data.guardada ? "no" : "si";
        star.setAttribute("aria-pressed", String(data.guardada));
        window.I18n.setAttribute(star, "aria-label", key);
        window.I18n.setAttribute(star, "title", key);
        if (data.guardada) star.setAttribute("data-save-effect", "saved");
      });
      window.I18n.setText(status, data.guardada ? "Pregunta guardada." : "Pregunta quitada de Guardadas.");
    } catch {
      status.classList.add("is-error");
      window.I18n.setText(status, "No pudimos confirmar el guardado. Recargá para comprobarlo.");
    } finally {
      clearTimeout(timeout);
      busy.delete(id);
      controls.forEach(control => {
        control.querySelector("button").disabled = false;
        control.removeAttribute("aria-busy");
      });
    }
  });
})();
