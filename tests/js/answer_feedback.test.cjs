// Pruebas de interacción del JS real con DOM simulado, sin navegador ni dependencias.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../../compilando/static/js/answers.js"), "utf8");
const result = (utilidad, cantidad_utiles) => ({
    respuesta_id: 7, utilidad, cantidad_utiles,
    mensaje: utilidad === null ? "Retiraste tu evaluación." : "Gracias por tu opinión.",
});
const response = (data, ok = true, type = "application/json") => ({
    ok, headers: { get: () => type }, json: async () => data,
});

function setup() {
    const events = {};
    const calls = [];
    const timers = new Map();
    let nextTimer = 0;
    let answer = async () => response(result(true, 1));
    const attributes = () => ({
        attrs: {},
        setAttribute(key, value) { this.attrs[key] = value; },
        removeAttribute(key) { delete this.attrs[key]; },
    });
    const status = {
        ...attributes(),
        classList: {
            values: new Set(),
            add(name) { this.values.add(name); },
            remove(name) { this.values.delete(name); },
        },
    };
    const doc = {
        body: {}, activeElement: null,
        addEventListener: (name, callback) => { (events[name] ||= []).push(callback); },
        querySelector: () => null, getElementById: () => null,
        createElement: () => ({ remove() { panel.count = null; } }),
    };
    const buttons = ["si", "no"].map(choice => ({
        ...attributes(), value: choice, dataset: { feedbackChoice: choice }, disabled: false,
        focus(options) { doc.activeElement = this; this.focusOptions = options; },
    }));
    const panel = {
        count: null,
        querySelector: name => name === ".answer-feedback-status" ? status : panel.count,
        append: element => { panel.count = element; },
    };
    const form = {
        ...attributes(), dataset: { respuestaId: "7" }, action: "/answers/7/feedback",
        matches: name => name === ".answer-feedback-form", closest: () => panel,
        querySelector: () => buttons[0], querySelectorAll: () => buttons,
        contains: element => buttons.includes(element),
    };
    const i18n = {
        setText(element, key, params = {}) {
            element.textContent = key.replace(/\{(\w+)\}/g, (_, name) => params[name]);
        },
        setAttribute(element, name, key) { element.setAttribute(name, key); },
    };
    const window = { fetch: true, I18n: i18n };
    vm.runInNewContext(source, {
        document: doc, window, AbortController,
        fetch: (...args) => { calls.push(args); return answer(...args); },
        FormData: class extends Map { constructor() { super([["csrf_token", "token-prueba"]]); } },
        setTimeout: callback => { timers.set(++nextTimer, callback); return nextTimer; },
        clearTimeout: timer => timers.delete(timer),
    });
    events.DOMContentLoaded[0]();
    return {
        doc, window, form, buttons, panel, status, calls, timers,
        respond: callback => { answer = callback; },
        submit(index = 0) {
            const event = { target: form, submitter: buttons[index], prevented: false,
                preventDefault() { this.prevented = true; } };
            this.lastEvent = event;
            return events.submit[0](event);
        },
    };
}

test("guarda, cambia y retira sin reemplazar la tarjeta ni perder el texto", async () => {
    const app = setup();
    const draft = { value: "Mi respuesta todavía sin publicar" };
    app.doc.activeElement = draft;
    for (const [index, state, count] of [[0, true, 1], [1, false, 0], [1, null, 0]]) {
        app.respond(async () => response(result(state, count)));
        await app.submit(index);
        assert.equal(app.buttons[0].attrs["aria-pressed"], String(state === true));
        assert.equal(app.buttons[1].attrs["aria-pressed"], String(state === false));
        assert.equal(Boolean(app.panel.count), count > 0);
        assert.equal(app.buttons[index].value, state === null ? "no" : "retirar");
        assert.equal(app.buttons[0].attrs["data-feedback-effect"], state === true ? "si" : undefined);
        assert.equal(app.buttons[1].attrs["data-feedback-effect"], state === false ? "no" : undefined);
        assert.equal(app.doc.activeElement, draft);
        assert.equal(draft.value, "Mi respuesta todavía sin publicar");
        assert.equal(app.timers.size, 0);
    }
    assert.equal(app.calls[0][1].body.get("csrf_token"), "token-prueba");
    assert.equal(app.calls[0][1].body.get("utilidad"), "si");
    assert.equal(app.calls[2][1].body.get("utilidad"), "retirar");
    assert.equal(app.status.textContent, "Retiraste tu evaluación.");
});

test("bloquea doble envío y permite seguir escribiendo durante la espera", async () => {
    const app = setup();
    let resolve;
    app.respond(() => new Promise(done => { resolve = done; }));
    app.doc.activeElement = app.buttons[0];
    const first = app.submit();
    assert.ok(app.buttons.every(button => button.disabled));
    assert.equal(app.status.textContent, "Guardando tu opinión…");
    assert.equal(app.buttons[0].attrs["data-feedback-effect"], undefined);
    await app.submit();
    assert.equal(app.calls.length, 1);
    const draft = { value: "Sigo escribiendo" };
    app.doc.activeElement = draft;
    resolve(response(result(true, 1)));
    await first;
    assert.equal(app.buttons[0].attrs["data-feedback-effect"], "si");
    assert.ok(app.buttons.every(button => !button.disabled));
    assert.equal(app.doc.activeElement, draft);
    assert.equal(app.form.attrs["aria-busy"], undefined);
});

test("sesión/formulario vencidos y errores de red no muestran una elección confirmada", async () => {
    for (const failure of [
        async () => response({ error: "Ingresá de nuevo para dar tu opinión." }, false),
        async () => response({ error: "Tu formulario venció." }, false),
        async () => response({}, true, "text/html"),
        async () => response({ ...result(true, 1), respuesta_id: 99 }),
        async () => { throw new Error("Conexión interrumpida"); },
    ]) {
        const app = setup();
        app.respond(failure);
        await app.submit();
        assert.equal(app.buttons[0].value, "si");
        assert.equal(app.buttons[0].attrs["aria-pressed"], undefined);
        assert.equal(app.panel.count, null);
        assert.ok(app.buttons.every(button => !button.attrs["data-feedback-effect"]));
        assert.ok(app.status.classList.values.has("is-error"));
        assert.ok(app.buttons.every(button => !button.disabled));
        assert.equal(app.status.textContent.includes("Gracias"), false);
        assert.equal(app.timers.size, 0);
    }
});

test("la delegación admite formularios de IA añadidos después de inicializar", async () => {
    const app = setup();
    app.form.dataset.respuestaId = "22";
    app.form.action = "/answers/22/feedback";
    app.respond(async () => response({ ...result(true, 3), respuesta_id: 22 }));
    await app.submit();
    assert.equal(app.calls[0][0], "/answers/22/feedback");
    assert.equal(app.panel.count.textContent, "A 3 personas les ayudó");
});

test("conserva el envío normal si fetch o el helper de idiomas no están disponibles", async () => {
    for (const dependency of ["fetch", "I18n"]) {
        const app = setup();
        app.window[dependency] = null;
        await app.submit();
        assert.equal(app.lastEvent.prevented, false);
        assert.equal(app.calls.length, 0);
        assert.ok(app.buttons.every(button => !button.disabled));
    }
});
