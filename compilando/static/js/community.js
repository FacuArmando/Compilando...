"use strict";

const composer = document.querySelector("#question-composer");

if (composer) {
  const host = composer.querySelector("[data-question-form-host]");
  const status = composer.querySelector("[data-composer-status]");
  const fallback = composer.querySelector("[data-composer-fallback]");
  let loaded = false;
  let loading = false;

  composer.querySelector("[data-close-composer]").addEventListener("click", () => {
    composer.open = false;
    composer.querySelector("summary").focus();
  });

  composer.addEventListener("toggle", async () => {
    if (!composer.open || loaded || loading) return;

    loading = true;
    status.hidden = false;
    window.I18n.setText(status, "Abriendo el formulario…");
    host.setAttribute("aria-busy", "true");
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);

    try {
      const response = await fetch(composer.dataset.formUrl, {
        credentials: "same-origin",
        headers: { Accept: "text/html" },
        signal: controller.signal,
      });

      if (response.status === 401) {
        window.I18n.setText(status, "Tu sesión venció. Iniciá sesión para continuar.");
        fallback.href = composer.dataset.loginUrl;
        window.I18n.setText(fallback, "Iniciar sesión");
        return;
      }
      if (!response.ok) throw new Error("No se pudo abrir el formulario.");

      const page = new DOMParser().parseFromString(await response.text(), "text/html");
      const original = page.querySelector("form.question-form");
      if (!original) throw new Error("No se encontró el formulario.");

      // Reutilizar el formulario del módulo de preguntas con todos sus campos y CSRF.
      const form = document.importNode(original, true);
      // El formulario original publica en su propia página; conservar ese destino aquí.
      form.action = new URL(original.getAttribute("action") || response.url, response.url).href;
      host.replaceChildren(form);
      window.iniciarAdjuntos?.(form);
      loaded = true;
      status.hidden = true;
      fallback.hidden = true;
      if (composer.open) form.querySelector("input[name='titulo']")?.focus({ preventScroll: true });
    } catch {
      window.I18n.setText(status, "No pudimos abrir el formulario acá. Podés continuar desde su página.");
    } finally {
      clearTimeout(timeout);
      loading = false;
      host.removeAttribute("aria-busy");
    }
  });

  const openRequestedComposer = () => {
    if (location.hash === "#question-composer") composer.open = true;
  };
  window.addEventListener("hashchange", openRequestedComposer);
  openRequestedComposer();
}

const account = document.querySelector(".community-account");
if (account) {
  document.addEventListener("click", (event) => {
    if (!account.contains(event.target)) account.open = false;
  });
  account.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      account.open = false;
      account.querySelector("summary").focus();
    }
  });
}

// Actualización en vivo en el inicio cuando la IA responde automáticamente una pregunta
(() => {
  const cards = Array.from(document.querySelectorAll(".community-question[data-pregunta-id]"));
  if (!cards.length) return;

  const ids = cards.map((card) => card.dataset.preguntaId).filter(Boolean);
  if (!ids.length) return;

  window.setInterval(async () => {
    try {
      const resp = await fetch(`/feed-ai-status?ids=${encodeURIComponent(ids.join(","))}`, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (!resp.ok) return;
      const data = await resp.json();
      if (!data.respuestas) return;

      cards.forEach((card) => {
        const id = card.dataset.preguntaId;
        const total = data.respuestas[id];
        if (typeof total !== "number" || total <= 0) return;

        const badge = card.querySelector("[data-feed-answer-count]");
        if (!badge || badge.classList.contains("has-answers")) return;

        badge.classList.add("has-answers");
        const iconSvg = badge.querySelector("svg");
        const texto = total === 1 ? "1 respuesta" : `${total} respuestas`;
        if (iconSvg) {
          badge.replaceChildren(iconSvg, ` ${texto}`);
        } else {
          badge.textContent = texto;
        }
        card.querySelector(".community-ai-badge")?.remove();
      });
    } catch (_) {
      // Silencioso ante cortes temporales de red
    }
  }, 5000);
})();
