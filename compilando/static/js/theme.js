/* Se carga antes de los estilos para recuperar el tema sin un destello claro. */
(() => {
  "use strict";
  const root = document.documentElement;
  const key = "compilando-theme";
  const system = matchMedia("(prefers-color-scheme: dark)");
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const valid = (value) => value === "dark" || value === "light";
  let preference = null;
  let changing = false;
  let activeTransition = null;

  try {
    const saved = localStorage.getItem(key);
    if (valid(saved)) preference = saved;
  } catch { /* El tema sigue funcionando cuando el navegador bloquea el almacenamiento. */ }

  const apply = (theme) => {
    root.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute(
      "content", theme === "dark" ? "#10141b" : "#f6f8fc"
    );
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.setAttribute("aria-checked", String(theme === "dark"));
      const label = theme === "dark" ? "Activar modo claro" : "Activar modo oscuro";
      if (window.I18n) {
        window.I18n.setAttribute(button, "title", label);
        window.I18n.setAttribute(button, "aria-label", "Modo oscuro");
      } else button.title = label;
    });
  };
  const preferred = () => preference || (system.matches ? "dark" : "light");
  apply(preferred());

  const toggle = async (button) => {
    if (changing) return;
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    preference = next;
    try { localStorage.setItem(key, next); } catch { /* Preferencia válida durante esta página. */ }
    if (reducedMotion.matches) {
      apply(next);
      return;
    }

    changing = true;
    button.setAttribute("aria-busy", "true");
    try {
      if (document.startViewTransition) {
        const bounds = button.getBoundingClientRect();
        const x = bounds.left + bounds.width / 2;
        const y = bounds.top + bounds.height / 2;
        const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
        root.style.setProperty("--theme-origin-x", `${x}px`);
        root.style.setProperty("--theme-origin-y", `${y}px`);
        root.style.setProperty("--theme-radius", `${Math.ceil(radius) + 4}px`);
        root.classList.add("theme-reveal");
        activeTransition = document.startViewTransition(() => apply(preferred()));
        // El navegador puede omitir la captura si la pestaña deja de estar visible.
        activeTransition.ready.catch(() => {});
        await activeTransition.finished;
      } else {
        root.classList.add("theme-fade");
        apply(next);
        await new Promise((resolve) => setTimeout(resolve, 1400));
      }
    } catch {
      apply(preferred());
    } finally {
      activeTransition = null;
      changing = false;
      root.classList.remove("theme-reveal", "theme-fade");
      button.removeAttribute("aria-busy");
    }
  };

  window.addEventListener("languagechange", () => apply(root.dataset.theme));
  document.addEventListener("DOMContentLoaded", () => {
    apply(preferred());
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.hidden = false;
      button.addEventListener("click", () => toggle(button));
    });
  }, { once: true });

  system.addEventListener("change", () => { if (!preference) apply(preferred()); });
  reducedMotion.addEventListener("change", () => {
    if (reducedMotion.matches) activeTransition?.skipTransition();
  });
  window.addEventListener("storage", (event) => {
    if (event.key !== key && event.key !== null) return;
    preference = valid(event.newValue) ? event.newValue : null;
    activeTransition?.skipTransition();
    apply(preferred());
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) activeTransition?.skipTransition();
  });
})();
