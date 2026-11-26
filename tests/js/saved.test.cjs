const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../../compilando/static/js/saved.js"), "utf8");

function element() {
  return {
    attrs: {}, children: [], classes: new Set(),
    setAttribute(name, value) { this.attrs[name] = value; },
    removeAttribute(name) { delete this.attrs[name]; },
    append(...children) { this.children.push(...children); },
  };
}
const response = (guardada = true) => ({ ok: true,
  headers: { get: () => "application/json" },
  json: async () => ({ pregunta_id: 7, guardada }),
});

function setup({ enabled = true, savedPage = false } = {}) {
  let listener; let nextTimer = 0; const timers = new Map(); const calls = [];
  const status = element();
  status.classList = { add: key => status.classes.add(key), remove: key => status.classes.delete(key) };
  const buttons = [element(), element()];
  buttons.forEach(button => { button.value = "si"; button.attrs["aria-pressed"] = "false"; });
  const forms = buttons.map(button => ({
    ...element(), action: "/questions/7/saved",
    dataset: { savedQuestion: "7", savedPage: String(savedPage) },
    matches: selector => selector === ".question-save-form",
    querySelector: () => button,
    closest: () => ({ querySelector: () => status }),
  }));
  const draft = { value: "Mi respuesta en curso" };
  const doc = { activeElement: draft,
    addEventListener(name, callback) { listener = callback; },
    querySelectorAll: () => forms, createElement: element,
  };
  let reply = async () => response();
  const window = { fetch: enabled, AbortController, location: { origin: "http://localhost" },
    I18n: {
      setText(node, key) {
        assert.ok(!buttons.includes(node), "no reemplazar el icono al actualizar su etiqueta");
        node.textContent = key; node.children = [];
      },
      setAttribute(node, name, key) { node.setAttribute(name, key); },
    },
  };
  vm.runInNewContext(source, {
    window, document: doc, URL, AbortController,
    fetch: (url, options) => { calls.push({ url, options }); return reply(); },
    FormData: class extends Map {
      constructor() { super([["csrf_token", "csrf-prueba"], ["volver", "/?page=2"]]); }
    },
    setTimeout: callback => { timers.set(++nextTimer, callback); return nextTimer; },
    clearTimeout: id => timers.delete(id),
  });
  return {
    buttons, forms, status, calls, timers, draft, doc,
    reply(callback) { reply = callback; },
    submit(index = 0) {
      const event = { target: forms[index], submitter: buttons[index], prevented: false,
        preventDefault() { this.prevented = true; } };
      this.lastEvent = event;
      return listener?.(event);
    },
  };
}

test("confirma guardar y quitar; sincroniza estrellas y conserva el formulario y borrador", async () => {
  const app = setup();
  await app.submit();
  assert.equal(app.calls[0].options.body.get("guardada"), "si");
  assert.equal(app.calls[0].options.body.get("csrf_token"), "csrf-prueba");
  assert.equal(app.calls[0].options.body.get("volver"), "/?page=2");
  for (const button of app.buttons) {
    assert.equal(button.attrs["aria-pressed"], "true");
    assert.equal(button.attrs["title"], "Quitar de Guardadas");
    assert.equal(button.value, "no");
    assert.equal(button.attrs["data-save-effect"], "saved");
  }
  app.reply(async () => response(false)); await app.submit();
  assert.equal(app.calls[1].options.body.get("guardada"), "no");
  assert.equal(app.buttons[0].attrs["aria-pressed"], "false");
  assert.equal(app.buttons[0].attrs["title"], "Guardar pregunta");
  assert.equal(app.buttons[0].value, "si");
  assert.equal(app.doc.activeElement, app.draft);
  assert.equal(app.draft.value, "Mi respuesta en curso");
});

test("bloquea doble envío y no cambia la estrella antes de confirmar", async () => {
  const app = setup(); let finish;
  app.reply(() => new Promise(resolve => { finish = resolve; }));
  const pending = app.submit(); await app.submit(1);
  assert.equal(app.calls.length, 1);
  assert.equal(app.buttons[0].attrs["aria-pressed"], "false");
  assert.equal(app.buttons[1].disabled, true);
  finish(response()); await pending;
  assert.equal(app.buttons[0].disabled, false);
  assert.equal(app.forms[0].attrs["aria-busy"], undefined);
  assert.equal(app.timers.size, 0);
});

test("errores y sesión vencida conservan la selección y ofrecen solo enlaces internos", async () => {
  for (const login_url of ["/auth/login", "https://ajeno.invalid/"]) {
    const app = setup();
    app.reply(async () => ({ ok: false, headers: { get: () => "application/json" },
      json: async () => ({ error: "Iniciá sesión", login_url }),
    }));
    await app.submit();
    assert.equal(app.buttons[0].attrs["aria-pressed"], "false");
    assert.equal(app.buttons[0].disabled, false);
    assert.equal(app.status.classes.has("is-error"), true);
    assert.equal(app.status.children.length > 0, login_url.startsWith("/"));
  }
});

test("red, contenido inesperado y timeout no muestran un guardado que no se confirmó", async () => {
  for (const kind of ["network", "html", "wrong-id", "timeout"]) {
    const app = setup();
    app.reply(async () => {
      if (kind === "network") throw new Error("offline");
      if (kind === "html") return { ok: true, headers: { get: () => "text/html" } };
      if (kind === "wrong-id") return { ok: true, headers: { get: () => "application/json" },
        json: async () => ({ pregunta_id: 99, guardada: true }) };
      return new Promise((resolve, reject) => {
        app.calls[0].options.signal.addEventListener("abort", () => reject(new Error("timeout")));
      });
    });
    const pending = app.submit();
    if (kind === "timeout") app.timers.values().next().value();
    await pending;
    assert.equal(app.buttons[0].attrs["aria-pressed"], "false");
    assert.equal(app.buttons[0].value, "si");
    assert.equal(app.buttons[0].disabled, false);
    assert.match(app.status.textContent, /No pudimos confirmar/);
    assert.equal(app.timers.size, 0);
  }
});

test("la colección y la alternativa sin fetch conservan POST normal con paginación del servidor", async () => {
  for (const config of [{ savedPage: true }, { enabled: false }]) {
    const app = setup(config); await app.submit();
    assert.equal(app.lastEvent.prevented, false);
    assert.equal(app.calls.length, 0);
  }
});
