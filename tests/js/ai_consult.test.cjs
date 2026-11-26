const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname,
  "../../compilando/static/js/ai-consult.js"), "utf8");
class Element {
  constructor() { this.attrs = {}; this.dataset = {}; this.children = []; this.events = {}; }
  addEventListener(name, callback) { this.events[name] = callback; }
  setAttribute(name, value) { this.attrs[name] = value; }
  removeAttribute(name) { delete this.attrs[name]; }
  append(...children) { this.children.push(...children); }
  set textContent(value) { this.text = value; this.children = []; }
  get textContent() { return (this.text || "") + this.children.map(child =>
    typeof child === "string" ? child : child.textContent).join(""); }
}
const result = () => ({ respuesta_id: 42, cantidad: 1, html: "server-rendered-answer" });
const response = (data = result(), ok = true, type = "application/json") => ({
  ok, json: async () => data, headers: { get: () => type },
});
function setup({ enabled = true } = {}) {
  const form = new Element(); form.dataset.aiState = "idle"; form.action = "/questions/1/ai";
  const button = new Element(); const label = new Element();
  const status = new Element(); const loading = new Element(); loading.hidden = true;
  const hint = new Element(); hint.hidden = true;
  const settings = new Element(); settings.disabled = false;
  const list = new Element(); const count = new Element();
  const draft = { value: "Mi explicación todavía sin publicar" };
  const empty = { removed: false, remove() { this.removed = true; } };
  const answer = new Element(); answer.id = "respuesta-42";
  const classes = new Set(); answer.classList = { add: value => classes.add(value) };
  const map = {
    'button[type="submit"]': button, ".ai-submit-label": label, ".ai-status": status,
    ".ai-loading": loading, ".ai-wait-hint": hint, ".ai-settings": settings,
  };
  let valid = true; let fragmentValid = true;
  form.querySelector = selector => map[selector];
  form.reportValidity = () => valid;
  const doc = {
    activeElement: draft,
    getElementById(id) {
      if (id === "form-consulta-ia") return form;
      if (id === "answer-list") return list;
      return list.children.find(child => child.id === id) || null;
    },
    querySelector: () => empty,
    querySelectorAll: () => [count],
    createElement: () => new Element(),
  };
  const timers = new Map(); let timerId = 0; const calls = [];
  let reply = async () => response();
  const window = { fetch: enabled, AbortController, location: { origin: "http://localhost" },
    I18n: { setText(element, key, params = {}) {
      element.textContent = key.replace(/\{(\w+)\}/g, (_, name) => params[name]);
      element.dataset.i18n = key;
    } },
  };
  vm.runInNewContext(source, {
    document: doc, window, URL, AbortController,
    fetch: (url, options) => { calls.push({ url, options }); return reply(); },
    FormData: class extends Map {
      constructor() {
        assert.equal(settings.disabled, false, "capturar las opciones antes de deshabilitarlas");
        super([["csrf_token", "csrf-prueba"], ["confirmar_envio", "si"], ["incluir_adjuntos", "si"]]);
      }
    },
    DOMParser: class {
      parseFromString() { return { getElementById: () => fragmentValid ? answer : null }; }
    },
    setTimeout: callback => { timers.set(++timerId, callback); return timerId; },
    clearTimeout: id => timers.delete(id),
  });
  return {
    form, button, label, status, loading, hint, settings, list, count, draft, doc, empty,
    calls, timers, classes,
    reply(callback) { reply = callback; }, invalid() { valid = false; },
    badFragment() { fragmentValid = false; },
    submit() {
      const event = { prevented: false, preventDefault() { this.prevented = true; } };
      return form.events.submit?.(event);
    },
  };
}

test("la espera conserva consentimiento, adjuntos, borrador y foco; evita envíos duplicados", async () => {
  const app = setup(); let resolve;
  app.reply(() => new Promise(done => { resolve = done; }));
  const pending = app.submit();
  assert.equal(app.form.dataset.aiState, "loading");
  assert.equal(app.loading.hidden, false); assert.equal(app.hint.hidden, false);
  assert.equal(app.button.disabled, true); assert.equal(app.settings.disabled, true);
  assert.equal(app.calls[0].options.body.get("confirmar_envio"), "si");
  assert.equal(app.calls[0].options.body.get("incluir_adjuntos"), "si");
  assert.equal(app.calls[0].options.body.get("csrf_token"), "csrf-prueba");
  assert.equal(app.label.textContent, "Generando…");
  assert.equal(app.doc.activeElement, app.draft);
  await app.submit(); assert.equal(app.calls.length, 1);
  resolve(response()); await pending;
  assert.equal(app.draft.value, "Mi explicación todavía sin publicar");
  assert.equal(app.doc.activeElement, app.draft);
});

test("la respuesta publicada actualiza la lista y ofrece un enlace sin saltos de foco", async () => {
  const app = setup(); await app.submit();
  assert.equal(app.form.dataset.aiState, "success");
  assert.equal(app.loading.hidden, true); assert.equal(app.hint.hidden, true);
  assert.equal(app.form.attrs["aria-busy"], undefined);
  assert.equal(app.button.disabled, true);
  assert.equal(app.label.textContent, "Respuesta de IA publicada");
  assert.equal(app.list.children.length, 1); assert.equal(app.empty.removed, true);
  assert.equal(app.classes.has("answer-ai-arrived"), true);
  assert.equal(app.count.textContent, "1 respuesta");
  assert.equal(app.status.children.at(-1).href, "#respuesta-42");
  assert.equal(app.status.children.at(-1).textContent, "Ver respuesta");
  await app.submit(); assert.equal(app.calls.length, 1);
  assert.equal(app.timers.size, 0);
});

test("un rechazo restablece las opciones y permite reintentar sin perder el borrador", async () => {
  const app = setup(); app.reply(async () => response({ error: "Límite alcanzado" }, false));
  await app.submit();
  assert.equal(app.form.dataset.aiState, "error");
  assert.equal(app.loading.hidden, true); assert.equal(app.settings.disabled, false);
  assert.equal(app.button.disabled, false); assert.equal(app.label.textContent, "Volver a intentar");
  assert.equal(app.status.textContent, "Límite alcanzado");
  app.reply(async () => response()); await app.submit();
  assert.equal(app.form.dataset.aiState, "success");
  assert.equal(app.list.children.length, 1);
});

test("sesión vencida ofrece solo enlaces internos y no marca éxito", async () => {
  for (const login_url of ["/auth/login?next=/questions/1", "https://ajeno.invalid/"]) {
    const app = setup();
    app.reply(async () => response({ error: "Iniciá sesión", login_url }, false));
    await app.submit();
    assert.equal(app.form.dataset.aiState, "error");
    assert.equal(app.status.children.length > 0, login_url.startsWith("/"));
    assert.equal(app.list.children.length, 0);
  }
});

test("errores de red, respuestas incompletas y HTML inesperado no anuncian éxito", async () => {
  for (const failure of ["red", "fragmento", "html"]) {
    const app = setup();
    if (failure === "red") app.reply(async () => { throw new Error("offline"); });
    if (failure === "html") app.reply(async () => response({}, false, "text/html"));
    if (failure === "fragmento") app.badFragment();
    await app.submit();
    assert.equal(app.form.dataset.aiState, "error");
    assert.match(app.status.textContent, /No pudimos confirmar/);
    assert.equal(app.list.children.length, 0);
    assert.equal(app.draft.value, "Mi explicación todavía sin publicar");
  }
});

test("un timeout retira la carga y mantiene el borrador", async () => {
  const app = setup();
  app.reply(() => new Promise((resolve, reject) => {
    app.calls[0].options.signal.addEventListener("abort", () => reject(new Error("timeout")));
  }));
  const pending = app.submit(); app.timers.values().next().value(); await pending;
  assert.equal(app.form.dataset.aiState, "error");
  assert.equal(app.loading.hidden, true); assert.equal(app.timers.size, 0);
  assert.match(app.status.textContent, /tu texto sigue en este formulario/);
});

test("sin confirmación válida no consulta; sin fetch deja el envío normal", async () => {
  const app = setup(); app.invalid(); await app.submit();
  assert.equal(app.calls.length, 0); assert.equal(app.form.dataset.aiState, "idle");
  const fallback = setup({ enabled: false });
  assert.equal(fallback.form.events.submit, undefined);
  assert.equal(fallback.form.dataset.aiState, "idle");
  assert.equal(fallback.loading.hidden, true);
});
