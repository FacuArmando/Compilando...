const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname,
  "../../compilando/static/js/search-autocomplete.js"), "utf8");

class Element {
  constructor() {
    this.children = []; this.attrs = {}; this.dataset = {}; this.events = {};
    this.hidden = false; this.value = ""; this.className = "";
  }
  addEventListener(type, callback) { (this.events[type] ||= []).push(callback); }
  setAttribute(key, value) { this.attrs[key] = value; }
  removeAttribute(key) { delete this.attrs[key]; }
  append(...children) { children.forEach(child => { child.parent = this; this.children.push(child); }); }
  replaceChildren(...children) {
    this.children.forEach(child => { child.parent = null; });
    this.children = []; this.append(...children); this.text = "";
  }
  set textContent(value) { this.replaceChildren(); this.text = value; }
  get textContent() { return this.text || this.children.map(child => child.textContent).join(""); }
  set innerHTML(value) { throw new Error("Los datos de usuarios deben renderizarse como texto"); }
  contains(child) { return child === this || this.children.some(node => node.contains(child)); }
  closest(selector) {
    if (this.className.split(" ").includes(selector.slice(1))) return this;
    return this.parent?.closest(selector) || null;
  }
  scrollIntoView() { this.scrolled = true; }
}

function emit(element, type, extra = {}) {
  const event = { target: element, defaultPrevented: false,
    preventDefault() { this.defaultPrevented = true; }, ...extra };
  for (let node = element; node; node = node.parent) {
    for (const callback of node.events[type] || []) callback(event);
  }
  return event;
}

const question = (id, title = `Java ${id}`) => ({
  id, titulo: title, categoria: "Programación", url: `/questions/${id}`,
});
const response = (items) => ({ ok: true, json: async () => ({ preguntas: items }) });
const deferred = () => {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
};

function setup({ fetchEnabled = true } = {}) {
  const doc = new Element();
  const form = new Element();
  const input = new Element();
  const category = new Element();
  const panel = new Element(); panel.hidden = true;
  const list = new Element(); list.id = "navbar-search-options";
  const message = new Element();
  const status = new Element();
  const all = new Element();
  panel.append(list, message, all); form.append(input, category, panel, status); doc.append(form);
  form.action = "http://localhost/#preguntas";
  form.dataset.suggestionsUrl = "/search/suggestions";
  form.querySelector = selector => ({
    '[name="q"]': input, '[name="categoria"]': category,
    ".community-search-suggestions": panel, '[role="listbox"]': list,
    ".community-search-message": message, '[role="status"]': status,
    ".community-search-all": all,
  })[selector];
  doc.querySelector = () => form;
  doc.createElement = () => new Element();
  doc.activeElement = input;
  const calls = []; const visits = []; const timers = new Map(); let timerId = 0;
  let reply = async () => response([question(1), question(2)]);
  const window = new Element();
  window.fetch = fetchEnabled; window.AbortController = AbortController;
  window.location = { href: "http://localhost/", assign: url => visits.push(url) };
  window.I18n = { setText(element, key, params = {}) {
    element.textContent = key.replace(/\{(\w+)\}/g, (_, name) => params[name]);
    element.dataset.i18n = key;
  } };
  vm.runInNewContext(source, {
    document: doc, window, URL, AbortController,
    fetch: (url, options) => { calls.push({ url, options }); return reply(url, options); },
    setTimeout(callback, delay) { timers.set(++timerId, { callback, delay }); return timerId; },
    clearTimeout: id => timers.delete(id),
  });
  return {
    doc, form, input, category, panel, list, message, status, all, calls, visits, window,
    reply(callback) { reply = callback; },
    type(value) { input.value = value; emit(input, "input"); },
    key(key, extra) { return emit(input, "keydown", { key, ...extra }); },
    async runTimers(delay = 240) {
      const pending = [];
      for (const [id, timer] of timers) if (timer.delay === delay) {
        timers.delete(id); pending.push(timer.callback());
      }
      await Promise.all(pending);
    },
  };
}

test("espera 3 caracteres y agrupa escritura; limita a cinco y trata HTML como texto", async () => {
  const app = setup();
  app.type("ja"); await app.runTimers(); assert.equal(app.calls.length, 0);
  app.reply(async () => response(Array.from({ length: 6 }, (_, i) =>
    question(i + 1, i === 0 ? "Java <script>alert(1)</script>" : `Java ${i}`))));
  app.type("jav"); app.type("java"); await app.runTimers();
  assert.equal(app.calls.length, 1);
  assert.equal(app.calls[0].url.searchParams.get("q"), "java");
  assert.equal(app.panel.hidden, false);
  assert.equal(app.list.children.length, 5);
  assert.match(app.list.children[0].textContent, /<script>alert\(1\)<\/script>/);
  assert.equal(app.input.attrs["role"], "combobox");
  assert.equal(app.input.attrs["aria-expanded"], "true");
  assert.equal(app.input.attrs["aria-activedescendant"], undefined);
  assert.equal(new URL(app.all.href).hash, "#preguntas");
  assert.equal(app.status.textContent, "5 preguntas sugeridas.");
});

test("Enter busca normalmente sin selección; flechas eligen y Enter abre la pregunta", async () => {
  const app = setup(); app.type("java"); await app.runTimers();
  assert.equal(app.key("Enter").defaultPrevented, false);
  assert.equal(app.key("ArrowDown").defaultPrevented, true);
  assert.equal(app.input.attrs["aria-activedescendant"], "navbar-search-option-0");
  app.key("ArrowUp");
  assert.equal(app.list.children[1].attrs["aria-selected"], "true");
  assert.equal(app.key("Enter").defaultPrevented, true);
  assert.deepEqual(app.visits, ["/questions/2"]);
  assert.equal(app.panel.hidden, true);
});

test("descarta respuestas antiguas aunque el servidor ignore la cancelación", async () => {
  const app = setup(); const slow = deferred();
  app.reply(() => slow.promise);
  app.type("java"); const pending = app.runTimers();
  app.reply(async () => response([question(9, "JavaScript")]));
  app.type("javascript"); await app.runTimers();
  assert.equal(app.calls[0].options.signal.aborted, true);
  slow.resolve(response([question(1, "Java antiguo")])); await pending;
  assert.match(app.list.textContent, /JavaScript/);
  assert.doesNotMatch(app.list.textContent, /antiguo/);
  app.type("ja"); await app.runTimers();
  assert.equal(app.panel.hidden, true);
  assert.equal(app.input.attrs["aria-activedescendant"], undefined);
});

test("actualiza categoría y enlace completo; el mouse abre sin robar el foco", async () => {
  const app = setup(); app.type("java"); await app.runTimers();
  app.category.value = "7"; app.doc.activeElement = app.category;
  emit(app.category, "change"); await app.runTimers();
  assert.equal(app.calls.at(-1).url.searchParams.get("categoria"), "7");
  assert.equal(new URL(app.all.href).searchParams.get("categoria"), "7");
  const title = app.list.children[0].children[0].children[0];
  assert.equal(emit(title, "pointerdown").defaultPrevented, true);
  emit(title, "click");
  assert.deepEqual(app.visits, ["/questions/1"]);
});

test("Escape, salir del formulario y enviar cierran; una respuesta tardía no reabre", async () => {
  const app = setup(); const slow = deferred(); app.reply(() => slow.promise);
  app.type("java"); const pending = app.runTimers();
  assert.equal(app.key("Escape").defaultPrevented, true);
  slow.resolve(response([question(1)])); await pending;
  assert.equal(app.panel.hidden, true);
  app.reply(async () => response([question(1)]));
  for (const dismiss of [
    () => emit(app.form, "focusout", { relatedTarget: null }),
    () => emit(app.doc, "pointerdown"),
    () => emit(app.form, "submit"),
  ]) {
    app.type("java"); await app.runTimers(); dismiss();
    assert.equal(app.panel.hidden, true);
    assert.equal(app.input.attrs["aria-expanded"], "false");
  }
});

test("vacío, error de red y URL inválida mantienen disponible la búsqueda completa", async () => {
  const app = setup();
  for (const reply of [
    async () => response([]),
    async () => { throw new Error("sin conexión"); },
    async () => response([{ ...question(1), url: "https://ajeno.invalid/" }]),
  ]) {
    app.reply(reply); app.type("java"); await app.runTimers();
    assert.equal(app.panel.hidden, false);
    assert.equal(app.message.hidden, false);
    assert.equal(app.list.children.length, 0);
    assert.equal(app.key("Enter").defaultPrevented, false);
    assert.equal(emit(app.form, "submit").defaultPrevented, false);
    assert.equal(app.input.attrs["aria-busy"], undefined);
  }
  assert.deepEqual(app.visits, []);
});

test("respeta composición de texto y corta consultas que no responden", async () => {
  const app = setup();
  emit(app.input, "compositionstart"); app.input.value = "java";
  emit(app.input, "input", { isComposing: true }); await app.runTimers();
  assert.equal(app.calls.length, 0);
  assert.equal(app.key("Enter", { isComposing: true }).defaultPrevented, false);
  app.reply((url, options) => new Promise((resolve, reject) => {
    options.signal.addEventListener("abort", () => reject(new Error("timeout")));
  }));
  emit(app.input, "compositionend"); const pending = app.runTimers();
  assert.equal(app.calls.length, 1);
  await app.runTimers(5000); await pending;
  assert.match(app.message.textContent, /no están disponibles/);
  assert.equal(app.input.attrs["aria-busy"], undefined);
});

test("sin fetch conserva el campo y el formulario originales", () => {
  const app = setup({ fetchEnabled: false });
  app.type("java");
  assert.equal(app.input.attrs["role"], undefined);
  assert.equal(app.panel.hidden, true);
  assert.equal(emit(app.form, "submit").defaultPrevented, false);
});
