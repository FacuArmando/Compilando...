/* Sugerencias públicas; el formulario sigue funcionando sin JavaScript ni red. */
(() => {
  "use strict";
  const form = document.querySelector(".community-navbar-search");
  if (!form || !window.fetch || !window.AbortController || !window.I18n) return;
  const input = form.querySelector('[name="q"]');
  const category = form.querySelector('[name="categoria"]');
  const panel = form.querySelector(".community-search-suggestions");
  const list = form.querySelector('[role="listbox"]');
  const message = form.querySelector(".community-search-message");
  const status = form.querySelector('[role="status"]');
  const all = form.querySelector(".community-search-all");
  let timer;
  let controller;
  let version = 0;
  let items = [];
  let active = -1;
  let composing = false;

  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-controls", list.id);
  input.setAttribute("aria-expanded", "false");
  input.setAttribute("autocomplete", "off");

  const say = (key, params = {}) => window.I18n.setText(status, key, params);
  const close = () => {
    clearTimeout(timer);
    controller?.abort();
    controller = null;
    version += 1;
    panel.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    input.removeAttribute("aria-busy");
    list.replaceChildren();
    status.replaceChildren();
    items = [];
    active = -1;
  };
  const eligible = () => {
    const query = input.value.trim();
    const length = Array.from(query).length;
    return length >= 3 && length <= 200 && query.split(/\s+/u).length <= 12;
  };
  const show = () => {
    const target = new URL(form.action, window.location.href);
    target.searchParams.set("q", input.value.trim());
    if (category.value) target.searchParams.set("categoria", category.value);
    else target.searchParams.delete("categoria");
    all.href = target.href;
    panel.hidden = false;
    input.setAttribute("aria-expanded", "true");
  };
  const showMessage = (key) => {
    message.hidden = false;
    window.I18n.setText(message, key);
    say(key);
    show();
  };
  const select = (index, scroll = true) => {
    active = index;
    Array.from(list.children).forEach((option, i) => {
      option.setAttribute("aria-selected", String(i === active));
    });
    const option = list.children[active];
    if (option) {
      input.setAttribute("aria-activedescendant", option.id);
      if (scroll) option.scrollIntoView({ block: "nearest" });
    }
  };
  const visit = (index) => {
    const item = items[index];
    if (!item) return;
    close();
    window.location.assign(item.url);
  };
  const render = () => {
    list.replaceChildren();
    message.hidden = true;
    items.forEach((item, index) => {
      const option = document.createElement("li");
      option.className = "community-search-option";
      option.id = `navbar-search-option-${index}`;
      option.dataset.suggestionIndex = String(index);
      option.setAttribute("role", "option");
      option.setAttribute("aria-selected", "false");
      const copy = document.createElement("span");
      copy.className = "community-search-option-copy";
      const title = document.createElement("span");
      title.className = "community-search-option-title";
      title.textContent = item.titulo;
      const label = document.createElement("span");
      label.className = "community-search-option-category";
      label.textContent = item.categoria;
      const arrow = document.createElement("span");
      arrow.className = "community-search-option-arrow";
      arrow.setAttribute("aria-hidden", "true");
      arrow.textContent = "↗";
      copy.append(title, label);
      option.append(copy, arrow);
      list.append(option);
    });
    if (!items.length) {
      showMessage("No encontramos coincidencias. Podés buscar con Enter.");
      return;
    }
    say(items.length === 1 ? "1 pregunta sugerida." : "{count} preguntas sugeridas.", {
      count: items.length,
    });
    show();
  };
  const load = async () => {
    const current = version;
    const query = input.value.trim();
    const filter = category.value;
    const pending = new AbortController();
    controller = pending;
    const timeout = setTimeout(() => pending.abort(), 5000);
    const isCurrent = () => current === version && query === input.value.trim()
      && filter === category.value && form.contains(document.activeElement);
    input.setAttribute("aria-busy", "true");
    say("Buscando preguntas…");
    try {
      const url = new URL(form.dataset.suggestionsUrl, window.location.href);
      url.searchParams.set("q", query);
      if (filter) url.searchParams.set("categoria", filter);
      const response = await fetch(url, {
        signal: pending.signal, headers: { Accept: "application/json" }, cache: "no-store",
      });
      if (!response.ok) throw new Error("suggestions");
      const data = await response.json();
      if (!isCurrent()) return;
      if (!Array.isArray(data.preguntas) || data.preguntas.some(item =>
        !Number.isSafeInteger(item.id) || item.id <= 0 || typeof item.titulo !== "string"
        || typeof item.categoria !== "string" || item.url !== `/questions/${item.id}`
      )) throw new Error("suggestions");
      items = data.preguntas.slice(0, 5);
      render();
    } catch {
      if (isCurrent()) showMessage("Las sugerencias no están disponibles. Podés buscar con Enter.");
    } finally {
      clearTimeout(timeout);
      if (current === version) {
        input.removeAttribute("aria-busy");
        controller = null;
      }
    }
  };
  const schedule = () => {
    close();
    if (!composing && eligible()) timer = setTimeout(load, 240);
  };

  input.addEventListener("input", (event) => {
    if (!event.isComposing) schedule();
  });
  input.addEventListener("focus", schedule);
  input.addEventListener("compositionstart", () => { composing = true; close(); });
  input.addEventListener("compositionend", () => { composing = false; schedule(); });
  category.addEventListener("change", schedule);
  input.addEventListener("keydown", (event) => {
    if (composing || event.isComposing || event.keyCode === 229) return;
    if (!panel.hidden && items.length && ["ArrowDown", "ArrowUp"].includes(event.key)) {
      event.preventDefault();
      const next = active < 0 ? (event.key === "ArrowDown" ? 0 : items.length - 1)
        : (active + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
      select(next);
    } else if (event.key === "Enter" && !panel.hidden && active >= 0) {
      event.preventDefault();
      visit(active);
    }
  });
  form.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !event.isComposing && !composing) {
      event.preventDefault();
      close();
    }
  });
  const optionIndex = (event) => {
    const option = event.target.closest(".community-search-option");
    return option && list.contains(option) ? Number(option.dataset.suggestionIndex) : -1;
  };
  list.addEventListener("pointerdown", (event) => {
    if (optionIndex(event) >= 0) event.preventDefault();
  });
  list.addEventListener("pointermove", (event) => {
    const index = optionIndex(event);
    if (index >= 0) select(index, false);
  });
  list.addEventListener("click", (event) => visit(optionIndex(event)));
  form.addEventListener("focusout", (event) => {
    if (!form.contains(event.relatedTarget)) close();
  });
  document.addEventListener("pointerdown", (event) => {
    if (!form.contains(event.target)) close();
  });
  form.addEventListener("submit", close);
  window.addEventListener("pagehide", close);
})();
