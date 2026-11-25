/* Only explicitly marked interface text is translated. User content stays untouched. */
(() => {
  "use strict";
  const catalog = window.CompilandoCatalog || {};
  const root = document.documentElement;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  let locale = root.lang === "en" ? "en" : "es";
  let frame = 0;
  let active = [];
  const alphabet = "01{}[]<>/\\#%+=_ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  const paramsOf = (element, name = "i18n") => {
    try { return JSON.parse(element.getAttribute(`data-${name}-params`) || "{}"); }
    catch { return {}; }
  };
  const t = (key, params = {}) => {
    const template = (locale === "en" ? catalog[key] : key) || key;
    return String(template).replace(/\{(\w+)\}/g, (token, name) =>
      Object.hasOwn(params, name) ? String(params[name]) : token);
  };
  const canonical = (message) => {
    if (Object.hasOwn(catalog, message)) return [message, {}];
    for (const [key, english] of Object.entries(catalog).sort(([a], [b]) => b.replace(/\{\w+\}/g, "").length - a.replace(/\{\w+\}/g, "").length)) {
      for (const template of [key, english]) {
        const names = [];
        const pattern = template.split(/(\{\w+\})/).map((part) => {
          if (/^\{\w+\}$/.test(part)) { names.push(part.slice(1, -1)); return "(.+?)"; }
          return part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        }).join("");
        const match = String(message).match(new RegExp(`^${pattern}$`));
        if (match) return [key, Object.fromEntries(names.map((name, i) => [name, match[i + 1]]))];
      }
    }
    return [String(message), {}];
  };
  // A child marker lets callers append links/icons without losing them on the next switch.
  const setText = (element, message, params) => {
    const [key, values] = params === undefined ? canonical(message) : [message, params];
    element.removeAttribute("data-i18n");
    element.removeAttribute("data-i18n-params");
    const label = document.createElement("span");
    label.dataset.i18n = key;
    label.dataset.i18nParams = JSON.stringify(values);
    label.textContent = t(key, values);
    element.replaceChildren(label);
  };
  const setAttribute = (element, name, key, params = {}) => {
    element.setAttribute(`data-i18n-${name}`, key);
    element.setAttribute(`data-i18n-${name}-params`, JSON.stringify(params));
    element.setAttribute(name, t(key, params));
  };
  const nodes = (scope, selector) => [
    ...(scope.matches?.(selector) ? [scope] : []), ...scope.querySelectorAll(selector),
  ];
  const hydrate = (scope = document) => {
    nodes(scope, "[data-i18n]").forEach((element) => {
      const key = element.dataset.i18n;
      if (!key) return;
      const value = t(key, paramsOf(element));
      if (element.textContent !== value) element.textContent = value;
    });
    ["title", "placeholder", "aria-label"].forEach((name) => {
      nodes(scope, `[data-i18n-${name}]`).forEach((element) => {
        element.setAttribute(name, t(element.getAttribute(`data-i18n-${name}`), paramsOf(element, `i18n-${name}`)));
      });
    });
    nodes(scope, "[data-i18n-date]").forEach((element) => {
      const raw = element.dataset.i18nDate;
      // Preserve stored calendar values: changing language must not shift the displayed date.
      const date = new Date(/Z$|[+-]\d\d:\d\d$/.test(raw) ? raw : `${raw}Z`);
      if (Number.isNaN(date.getTime())) return;
      const long = element.dataset.dateStyle === "long";
      const options = long
        ? { weekday: "long", day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" }
        : { day: "2-digit", month: locale === "es" ? "2-digit" : "short", year: "numeric" };
      const value = new Intl.DateTimeFormat(locale === "es" ? "es-AR" : "en-GB", { ...options, timeZone: "UTC" }).format(date);
      if (element.textContent !== value) element.textContent = value;
    });
  };
  const finish = () => {
    cancelAnimationFrame(frame);
    active.forEach(({ element, value, attribute, textOnly }) => {
      if (!element.isConnected) return;
      if (attribute) element.setAttribute(attribute, value);
      else if (textOnly) element.textContent = value;
      else { element.replaceChildren(value); element.classList.remove("language-decoding"); }
    });
    active = [];
    root.classList.remove("language-changing");
    document.querySelectorAll("[data-language-toggle]").forEach((button) => button.removeAttribute("aria-busy"));
  };
  const scramble = (value, progress) => Array.from(value).map((char, index, chars) => {
    if (/\s/.test(char) || index / chars.length < progress) return char;
    return alphabet[Math.floor(Math.random() * alphabet.length)];
  }).join("");
  const draw = (now) => {
    let pending = false;
    active.forEach((item) => {
      if (item.textOnly && !item.element.selected) {
        item.element.textContent = item.value;
        return;
      }
      const progress = Math.max(0, Math.min(1, (now - item.start) / 900));
      if (progress < 1) pending = true;
      if (now - item.last < 40 && progress < 1) return;
      item.last = now;
      const text = scramble(item.value, progress);
      if (item.attribute) item.element.setAttribute(item.attribute, text);
      else if (item.textOnly) item.element.textContent = text;
      else item.overlay.textContent = text;
    });
    if (pending) frame = requestAnimationFrame(draw);
    else finish();
  };
  const updateControls = () => {
    document.querySelectorAll("[data-language-toggle]").forEach((button) => {
      button.hidden = false;
      button.setAttribute("aria-checked", String(locale === "en"));
      button.title = t(locale === "en" ? "Cambiar idioma a castellano" : "Cambiar idioma a inglés");
      button.setAttribute("aria-label", t("Idioma inglés"));
    });
  };
  const change = () => {
    finish();
    locale = locale === "es" ? "en" : "es";
    document.cookie = `compilando-language=${locale}; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`;
    root.lang = locale;
    hydrate();
    updateControls();
    window.dispatchEvent(new CustomEvent("languagechange", { detail: { language: locale } }));
    const announcement = document.querySelector(".language-announcement");
    if (announcement) announcement.textContent = t(locale === "en" ? "Idioma cambiado a inglés" : "Idioma cambiado a castellano");
    if (reduced.matches || document.hidden) return;
    const started = performance.now();
    document.querySelectorAll("span[data-i18n]").forEach((element) => {
      if (element.closest("pre, code, textarea, [hidden], [aria-hidden='true']") || !element.checkVisibility()) return;
      const rect = element.getBoundingClientRect();
      if (rect.bottom < 0 || rect.top > innerHeight || rect.right < 0 || rect.left > innerWidth) return;
      const value = element.textContent;
      if (!value || active.length >= 250) return;
      const text = document.createElement("span");
      text.className = "language-final";
      text.textContent = value;
      const overlay = document.createElement("span");
      overlay.className = "language-scramble";
      overlay.setAttribute("aria-hidden", "true");
      element.classList.add("language-decoding");
      element.replaceChildren(text, overlay);
      active.push({ element, value, overlay, start: started + Math.random() * 140, last: 0 });
    });
    document.querySelectorAll(".community-navbar-search input[data-i18n-placeholder]").forEach((element) => {
      if (element.value || !element.checkVisibility() || active.length >= 250) return;
      const rect = element.getBoundingClientRect();
      if (rect.bottom < 0 || rect.top > innerHeight || rect.right < 0 || rect.left > innerWidth) return;
      const value = element.getAttribute("placeholder");
      if (!value) return;
      element.setAttribute("placeholder", scramble(value, 0));
      active.push({ element, value, attribute: "placeholder", start: started, last: 0 });
    });
    document.querySelectorAll(".community-navbar-search select").forEach((select) => {
      const element = select.selectedOptions[0];
      if (!element?.matches("[data-i18n]") || !select.checkVisibility() || active.length >= 250) return;
      const rect = select.getBoundingClientRect();
      if (rect.bottom < 0 || rect.top > innerHeight || rect.right < 0 || rect.left > innerWidth) return;
      const value = element.textContent;
      if (!value) return;
      element.textContent = scramble(value, 0);
      active.push({ element, value, textOnly: true, start: started, last: 0 });
    });
    if (active.length) {
      root.classList.add("language-changing");
      document.querySelectorAll("[data-language-toggle]").forEach((button) => button.setAttribute("aria-busy", "true"));
      frame = requestAnimationFrame(draw);
    }
  };
  window.I18n = { t, setText, setAttribute, hydrate, get language() { return locale; } };
  hydrate();
  updateControls();
  document.querySelectorAll("[data-language-toggle]").forEach((button) => button.addEventListener("click", change));
  // New forms and AI answers may arrive after the language was changed, even mid-request.
  new MutationObserver((records) => {
    records.forEach(({ addedNodes }) => addedNodes.forEach((node) => {
      if (node.nodeType !== Node.ELEMENT_NODE || node.closest(".language-decoding")) return;
      hydrate(node);
    }));
  }).observe(document.body, { childList: true, subtree: true });
  reduced.addEventListener("change", finish);
  document.addEventListener("visibilitychange", () => { if (document.hidden) finish(); });
})();
