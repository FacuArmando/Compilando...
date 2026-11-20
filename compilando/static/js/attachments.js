"use strict";

// También se inicializa cuando el inicio inserta el formulario de preguntas.
window.iniciarAdjuntos = (root = document) => {
  root.querySelectorAll("[data-attachment-picker]").forEach((picker) => {
    if (picker.dataset.ready) return;
    // Sin esta API, conservar el selector nativo: el servidor valida igualmente.
    try { new DataTransfer(); } catch { return; }
    picker.dataset.ready = "true";
    picker.classList.add("attachments-enhanced");

    const input = picker.querySelector("input[type=file]");
    const zone = picker.querySelector("[data-dropzone]");
    const list = picker.querySelector("[data-attachment-list]");
    const error = picker.querySelector("[data-attachment-error]");
    const status = picker.querySelector("[data-attachment-status]");
    const maxFiles = Number(picker.dataset.maxFiles);
    const maxBytes = Number(picker.dataset.maxBytes);
    const maxTotal = Number(picker.dataset.maxTotal);
    const maxName = Number(picker.dataset.maxName);
    const extensions = input.accept.toLowerCase().split(",");
    let files = [];
    let busy = false;
    const size = (bytes) => {
      if (bytes < 1024) return `${bytes} B`;
      return bytes < 1024 * 1024
        ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1048576).toFixed(1)} MB`;
    };

    const showError = (message = "") => {
      window.I18n.setText(error, message);
      error.hidden = !message;
      input.setAttribute("aria-invalid", String(Boolean(message)));
    };
    const sync = () => {
      const selection = new DataTransfer();
      files.forEach((file) => selection.items.add(file));
      input.files = selection.files;
    };
    const render = () => {
      list.replaceChildren();
      files.forEach((file, index) => {
        const card = document.createElement("li");
        card.className = "attachment-card";
        const symbol = document.createElement("span");
        symbol.className = "attachment-symbol";
        symbol.textContent = "</>";
        symbol.setAttribute("aria-hidden", "true");
        const info = document.createElement("div");
        info.className = "attachment-info";
        const name = document.createElement("strong");
        name.textContent = file.name;
        const detail = document.createElement("small");
        detail.textContent = size(file.size);
        info.append(name, detail);
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "attachment-remove";
        remove.textContent = "×";
        window.I18n.setAttribute(remove, "aria-label", "Quitar {name}", { name: file.name });
        remove.addEventListener("click", () => {
          files.splice(index, 1);
          sync();
          render();
          showError();
          const next = list.querySelectorAll("button")[Math.min(index, files.length - 1)];
          (next || input).focus();
        });
        card.append(symbol, info, remove);
        list.append(card);
      });
      window.I18n.setText(status, files.length
        ? `${files.length} de ${maxFiles} archivos · ${size(files.reduce((sum, f) => sum + f.size, 0))} en total.`
        : "Sin archivos seleccionados.");
    };
    const setBusy = (value) => {
      busy = value;
      picker.dataset.validating = String(value);
      picker.setAttribute("aria-busy", String(value));
      input.disabled = value;
      list.querySelectorAll("button").forEach((button) => { button.disabled = value; });
      if (value) window.I18n.setText(status, "Revisando los archivos antes de agregarlos…");
    };
    const add = async (incoming) => {
      if (busy) {
        showError("Esperá a que termine la revisión antes de agregar más archivos.");
        sync();
        return;
      }
      const candidate = [...files, ...incoming];
      let message = "";
      if (candidate.length > maxFiles) message = `Podés adjuntar hasta ${maxFiles} archivos.`;
      for (const file of candidate) {
        if (message) break;
        const name = file.name.replaceAll("\\", "/").split("/").at(-1);
        const dot = name.lastIndexOf(".");
        if (!name || Array.from(name).length > maxName || /[\p{Cc}\p{Cf}]/u.test(name)) {
          message = `Usá nombres de hasta ${maxName} caracteres, sin caracteres invisibles o de control.`;
        } else if (!extensions.includes(name.slice(dot).toLowerCase()) || dot <= 0) {
          message = `${file.name}: elegí un archivo ${extensions.join(", ")}.`;
        } else if (!file.size) {
          message = `${file.name}: el archivo está vacío.`;
        } else if (file.size > maxBytes) {
          message = `${file.name}: el máximo por archivo es ${size(maxBytes)}.`;
        }
      }
      if (!message && candidate.reduce((sum, f) => sum + f.size, 0) > maxTotal) {
        message = `Los archivos juntos no pueden superar ${size(maxTotal)}.`;
      }
      if (!message) {
        setBusy(true);
        try {
          for (const file of incoming) {
            const bytes = await file.arrayBuffer();
            let text;
            try {
              text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
            } catch {
              message = `${file.name}: guardá el archivo como texto UTF-8.`;
              break;
            }
            if (!text) {
              message = `${file.name}: el archivo está vacío.`;
              break;
            }
            if (/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F]/u.test(text)) {
              message = `${file.name}: debe contener texto, sin datos binarios.`;
              break;
            }
          }
        } catch {
          message = "No pudimos leer uno de los archivos. Volvé a seleccionarlo desde tu equipo.";
        } finally {
          setBusy(false);
        }
      }
      if (!message) files = candidate;
      sync();
      render();
      showError(message);
    };
    input.addEventListener("change", () => add(Array.from(input.files)));
    zone.addEventListener("dragover", (event) => {
      if (!event.dataTransfer.types.includes("Files")) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
      zone.classList.add("is-dragging");
    });
    zone.addEventListener("dragleave", (event) => {
      if (!zone.contains(event.relatedTarget)) zone.classList.remove("is-dragging");
    });
    zone.addEventListener("drop", (event) => {
      event.preventDefault();
      zone.classList.remove("is-dragging");
      const hasDirectory = Array.from(event.dataTransfer.items).some(
        (item) => item.webkitGetAsEntry?.()?.isDirectory
      );
      if (hasDirectory) {
        showError("Arrastrá archivos individuales, no carpetas.");
        return;
      }
      const incoming = Array.from(event.dataTransfer.files);
      if (incoming.length) add(incoming);
      else showError("Arrastrá archivos individuales, no carpetas.");
    });
    input.form.addEventListener("reset", (event) => {
      if (busy) {
        event.preventDefault();
        return;
      }
      files = [];
      showError();
      render();
    });
    input.form.addEventListener("submit", (event) => {
      if (!busy) return;
      event.preventDefault();
      showError("Esperá a que termine la revisión de archivos y volvé a publicar.");
    });
    render();
  });
};

window.iniciarAdjuntos();
