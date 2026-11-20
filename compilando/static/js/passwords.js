"use strict";

document.querySelectorAll("[data-password-toggle]").forEach((button) => {
  const input = document.getElementById(button.dataset.passwordToggle);
  if (!input) return;
  button.hidden = false;
  button.addEventListener("click", () => {
    const visible = input.type === "password";
    input.type = visible ? "text" : "password";
    window.I18n.setText(button, visible ? "Ocultar contraseña" : "Mostrar contraseña");
    button.setAttribute("aria-pressed", String(visible));
  });
});

const passwordForm = document.querySelector(".account-password-form");
if (passwordForm) {
  const nueva = passwordForm.querySelector("#password-nueva");
  const confirmacion = passwordForm.querySelector("#password-confirmacion");
  const lengthError = passwordForm.querySelector("#password-length-error");
  const matchError = passwordForm.querySelector("#password-match-error");
  let lengthReviewed = false;

  const mostrarError = (input, element, message, visible = true) => {
    input.setCustomValidity(window.I18n.t(message));
    window.I18n.setText(element, message);
    element.hidden = !message || !visible;
    if (message && visible) input.setAttribute("aria-invalid", "true");
    else input.removeAttribute("aria-invalid");
  };

  const validarLongitud = () => {
    // Contar caracteres completos, igual que Python, sin recortar lo que se escribió.
    const longitud = Array.from(nueva.value).length;
    const invalida = nueva.value && (longitud < 8 || longitud > 18 || !nueva.value.trim());
    mostrarError(nueva, lengthError,
      invalida ? "La nueva contraseña debe tener entre 8 y 18 caracteres." : "",
      lengthReviewed || longitud > 18);
  };

  const validarCoincidencia = () => {
    const distintas = confirmacion.value && nueva.value !== confirmacion.value;
    mostrarError(confirmacion, matchError,
      distintas ? "Las contraseñas no coinciden." : "");
  };

  const validar = () => {
    validarLongitud();
    validarCoincidencia();
  };

  window.addEventListener("languagechange", validar);
  nueva.addEventListener("input", validar);
  nueva.addEventListener("change", validar);
  confirmacion.addEventListener("input", validarCoincidencia);
  confirmacion.addEventListener("change", validarCoincidencia);
  nueva.addEventListener("blur", () => {
    lengthReviewed = true;
    validarLongitud();
  });
  nueva.addEventListener("invalid", () => {
    lengthReviewed = true;
    validarLongitud();
  });
  passwordForm.addEventListener("submit", (event) => {
    lengthReviewed = true;
    validar();
    if (!passwordForm.checkValidity()) {
      event.preventDefault();
      passwordForm.reportValidity();
    }
  });
}
