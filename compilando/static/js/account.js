"use strict";

const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
const RING_CIRC = 263.89;

function animateNumber(el, target) {
  const prefix = el.dataset.prefix || "";
  const suffix = el.dataset.suffix || "";
  const current = Number(el.dataset.currentValue ?? 0);
  el.dataset.currentValue = String(target);

  if (reducedMotion.matches || current === target) {
    el.textContent = `${prefix}${target}${suffix}`;
    return;
  }

  const duration = 850;
  const start = performance.now();
  const step = (now) => {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    const value = Math.round(current + (target - current) * eased);
    el.textContent = `${prefix}${value}${suffix}`;
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// Animación inicial al abrir Mi cuenta
document.querySelectorAll("[data-count-target]").forEach((el) => {
  const target = Number(el.dataset.countTarget) || 0;
  el.dataset.currentValue = "0";
  animateNumber(el, target);
});

// Actualización automática en segundo plano (al volver a la pestaña o cada 15s)
const statsSection = document.querySelector("[data-stats-url]");
if (statsSection) {
  const statsUrl = statsSection.dataset.statsUrl;
  const ringEl = statsSection.querySelector("[data-ring-progress]");
  const ratioEl = statsSection.querySelector("[data-stat-ratio]");

  const refreshStats = async () => {
    if (document.hidden) return;
    try {
      const res = await fetch(statsUrl, { headers: { Accept: "application/json" } });
      if (!res.ok) return;
      const data = await res.json();

      statsSection.querySelectorAll("[data-stat-key]").forEach((el) => {
        const key = el.dataset.statKey;
        if (key in data) animateNumber(el, Number(data[key]) || 0);
      });

      if (ratioEl) {
        ratioEl.textContent = `${data.respuestas_aceptadas}/${data.respuestas_totales}`;
      }
      if (ringEl) {
        const pct = Number(data.porcentaje_aceptadas) || 0;
        const offset = RING_CIRC - (RING_CIRC * pct) / 100;
        ringEl.style.setProperty("--ring-offset", String(offset));
        ringEl.style.strokeDashoffset = String(offset);
      }
    } catch {
      // Ignorar fallos temporales de red
    }
  };

  document.addEventListener("visibilitychange", refreshStats);
  window.addEventListener("pageshow", refreshStats);
  setInterval(refreshStats, 15000);
}

// Globos festivos cuando es el cumpleaños del usuario
const balloonContainer = document.querySelector("[data-birthday-balloons]");

const balloonShapes = [
  // 1. Pingüino Tux (Linux)
  `<svg viewBox="0 0 64 78" aria-hidden="true"><ellipse cx="32" cy="36" rx="22" ry="28" fill="#1e293b"/><ellipse cx="32" cy="41" rx="14" ry="19" fill="#f8fafc"/><circle cx="26" cy="24" r="3" fill="#fff"/><circle cx="38" cy="24" r="3" fill="#fff"/><circle cx="27" cy="24" r="1.5" fill="#0f172a"/><circle cx="37" cy="24" r="1.5" fill="#0f172a"/><polygon points="27,30 37,30 32,36" fill="#f59e0b"/><ellipse cx="22" cy="62" rx="7" ry="4" fill="#f59e0b"/><ellipse cx="42" cy="62" rx="7" ry="4" fill="#f59e0b"/><line x1="32" y1="64" x2="32" y2="78" stroke="#94a3b8" stroke-width="1.5"/></svg>`,
  // 2. Terminal >_
  `<svg viewBox="0 0 64 78" aria-hidden="true"><rect x="10" y="14" width="44" height="30" rx="5" fill="#2563eb"/><rect x="14" y="18" width="36" height="22" rx="2" fill="#0f172a"/><text x="32" y="33" text-anchor="middle" fill="#38bdf8" font-family="monospace" font-size="11" font-weight="bold">&gt;_</text><path d="M 4 44 L 60 44 L 55 51 L 9 51 Z" fill="#64748b"/><line x1="32" y1="51" x2="32" y2="78" stroke="#94a3b8" stroke-width="1.5"/></svg>`,
  // 3. Etiquetas </>
  `<svg viewBox="0 0 64 78" aria-hidden="true"><ellipse cx="32" cy="30" rx="24" ry="27" fill="#10b981"/><polygon points="28,56 36,56 32,62" fill="#10b981"/><text x="32" y="35" text-anchor="middle" fill="#ffffff" font-family="monospace" font-size="15" font-weight="bold">&lt;/&gt;</text><line x1="32" y1="62" x2="32" y2="78" stroke="#94a3b8" stroke-width="1.5"/></svg>`,
  // 4. Llaves { }
  `<svg viewBox="0 0 64 78" aria-hidden="true"><ellipse cx="32" cy="30" rx="24" ry="27" fill="#8b5cf6"/><polygon points="28,56 36,56 32,62" fill="#8b5cf6"/><text x="32" y="35" text-anchor="middle" fill="#ffffff" font-family="monospace" font-size="17" font-weight="bold">{ }</text><line x1="32" y1="62" x2="32" y2="78" stroke="#94a3b8" stroke-width="1.5"/></svg>`,
  // 5. Binario 0101
  `<svg viewBox="0 0 64 78" aria-hidden="true"><ellipse cx="32" cy="30" rx="24" ry="27" fill="#f59e0b"/><polygon points="28,56 36,56 32,62" fill="#f59e0b"/><text x="32" y="36" text-anchor="middle" fill="#ffffff" font-family="monospace" font-size="14" font-weight="bold">0101</text><line x1="32" y1="62" x2="32" y2="78" stroke="#94a3b8" stroke-width="1.5"/></svg>`,
  // 6. Python (azul y amarillo)
  `<svg viewBox="0 0 64 78" aria-hidden="true"><ellipse cx="32" cy="30" rx="24" ry="27" fill="#1e293b"/><polygon points="28,56 36,56 32,62" fill="#1e293b"/><path d="M31 15h7a5 5 0 0 1 5 5v6H28v2h13a4 4 0 0 1 4 4v5a5 5 0 0 1-5 5h-6v-5h-7v-7h12v-2H26a5 5 0 0 1-5-5v-3a5 5 0 0 1 5-5z" fill="#3776ab"/><path d="M33 45h-7a5 5 0 0 1-5-5v-6h15v-2H23a4 4 0 0 1-4-4v-5a5 5 0 0 1 5-5h6v5h7v7H25v2h13a5 5 0 0 1 5 5v3a5 5 0 0 1-5 5z" fill="#ffd43b"/><circle cx="28" cy="19" r="1.5" fill="#fff"/><circle cx="36" cy="41" r="1.5" fill="#1e293b"/><line x1="32" y1="62" x2="32" y2="78" stroke="#94a3b8" stroke-width="1.5"/></svg>`,
  // 7. Computadora / IDE
  `<svg viewBox="0 0 64 78" aria-hidden="true"><rect x="11" y="12" width="42" height="29" rx="4" fill="#0ea5e9"/><rect x="15" y="16" width="34" height="21" rx="2" fill="#0f172a"/><rect x="18" y="20" width="14" height="2.5" rx="1" fill="#38bdf8"/><rect x="18" y="25" width="22" height="2.5" rx="1" fill="#a78bfa"/><rect x="18" y="30" width="18" height="2.5" rx="1" fill="#34d399"/><rect x="27" y="41" width="10" height="6" fill="#64748b"/><rect x="20" y="47" width="24" height="3" rx="1.5" fill="#94a3b8"/><line x1="32" y1="50" x2="32" y2="78" stroke="#94a3b8" stroke-width="1.5"/></svg>`,
  // 8. Rama Git
  `<svg viewBox="0 0 64 78" aria-hidden="true"><ellipse cx="32" cy="30" rx="24" ry="27" fill="#ef4444"/><polygon points="28,56 36,56 32,62" fill="#ef4444"/><circle cx="24" cy="20" r="3.5" fill="#fff"/><circle cx="24" cy="40" r="3.5" fill="#fff"/><circle cx="40" cy="26" r="3.5" fill="#fff"/><line x1="24" y1="23.5" x2="24" y2="36.5" stroke="#fff" stroke-width="2.5"/><path d="M24 34 C24 28, 40 31, 40 28.5" fill="none" stroke="#fff" stroke-width="2.5"/><line x1="32" y1="62" x2="32" y2="78" stroke="#94a3b8" stroke-width="1.5"/></svg>`,
  // 9. Ubuntu (círculo naranja con 3 nodos)
  `<svg viewBox="0 0 64 78" aria-hidden="true"><ellipse cx="32" cy="30" rx="24" ry="27" fill="#e95420"/><polygon points="28,56 36,56 32,62" fill="#e95420"/><circle cx="32" cy="30" r="10" fill="none" stroke="#ffffff" stroke-width="3"/><circle cx="20" cy="30" r="3.3" fill="#ffffff" stroke="#e95420" stroke-width="1.5"/><circle cx="38" cy="19.6" r="3.3" fill="#ffffff" stroke="#e95420" stroke-width="1.5"/><circle cx="38" cy="40.4" r="3.3" fill="#ffffff" stroke="#e95420" stroke-width="1.5"/><line x1="32" y1="62" x2="32" y2="78" stroke="#94a3b8" stroke-width="1.5"/></svg>`,
  // 10. Lenguaje C (hexágono azul con C)
  `<svg viewBox="0 0 64 78" aria-hidden="true"><ellipse cx="32" cy="30" rx="24" ry="27" fill="#00599c"/><polygon points="28,56 36,56 32,62" fill="#00599c"/><polygon points="32,14 46,22 46,38 32,46 18,38 18,22" fill="#004482" stroke="#659ad2" stroke-width="2"/><text x="32" y="36" text-anchor="middle" fill="#ffffff" font-family="sans-serif" font-size="18" font-weight="bold">C</text><line x1="32" y1="62" x2="32" y2="78" stroke="#94a3b8" stroke-width="1.5"/></svg>`,
  // 11. Java (taza de café y vapor)
  `<svg viewBox="0 0 64 78" aria-hidden="true"><ellipse cx="32" cy="30" rx="24" ry="27" fill="#1e293b"/><polygon points="28,56 36,56 32,62" fill="#1e293b"/><path d="M27 21 C25 18, 29 16, 27 13" fill="none" stroke="#f89820" stroke-width="2" stroke-linecap="round"/><path d="M35 21 C33 18, 37 16, 35 13" fill="none" stroke="#f89820" stroke-width="2" stroke-linecap="round"/><path d="M21 25 H41 V34 C41 39, 21 39, 21 34 Z" fill="#5382a1"/><path d="M41 27 H44 C46 27, 46 33, 44 33 H41" fill="none" stroke="#5382a1" stroke-width="2.2"/><ellipse cx="31" cy="41" rx="13" ry="2.5" fill="#f89820"/><line x1="32" y1="62" x2="32" y2="78" stroke="#94a3b8" stroke-width="1.5"/></svg>`,
  // 12. Haskell (símbolo >>= λ)
  `<svg viewBox="0 0 64 78" aria-hidden="true"><ellipse cx="32" cy="30" rx="24" ry="27" fill="#5e5086"/><polygon points="28,56 36,56 32,62" fill="#5e5086"/><polyline points="17,21 24,30 17,39" fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><polyline points="25,21 32,30 25,39" fill="none" stroke="#d8b4fe" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><line x1="36" y1="27" x2="46" y2="27" stroke="#ffffff" stroke-width="2.8" stroke-linecap="round"/><line x1="39" y1="33" x2="46" y2="33" stroke="#ffffff" stroke-width="2.8" stroke-linecap="round"/><line x1="32" y1="62" x2="32" y2="78" stroke="#94a3b8" stroke-width="1.5"/></svg>`,
  // 13. Avatar de programador (auriculares y anteojos)
  `<svg viewBox="0 0 64 78" aria-hidden="true"><ellipse cx="32" cy="30" rx="24" ry="27" fill="#0f766e"/><polygon points="28,56 36,56 32,62" fill="#0f766e"/><path d="M19 30 A13 13 0 0 1 45 30" fill="none" stroke="#38bdf8" stroke-width="3"/><rect x="16" y="26" width="4" height="9" rx="2" fill="#38bdf8"/><rect x="44" y="26" width="4" height="9" rx="2" fill="#38bdf8"/><circle cx="32" cy="30" r="10" fill="#fde68a"/><path d="M22 28 C22 20, 42 20, 42 28 C38 24, 26 24, 22 28 Z" fill="#1e293b"/><rect x="24" y="28" width="6" height="4" rx="1" fill="#0f172a"/><rect x="34" y="28" width="6" height="4" rx="1" fill="#0f172a"/><line x1="30" y1="30" x2="34" y2="30" stroke="#0f172a" stroke-width="1.5"/><path d="M21 46 C23 41, 41 41, 43 46 Z" fill="#38bdf8"/><line x1="32" y1="62" x2="32" y2="78" stroke="#94a3b8" stroke-width="1.5"/></svg>`,
];


function launchBalloons() {
  if (!balloonContainer) return;
  balloonContainer.replaceChildren();
  if (reducedMotion.matches) return;

  const count = window.innerWidth < 720 ? 16 : 34;
  const balloons = document.createDocumentFragment();
  for (let i = 0; i < count; i++) {
    const balloon = document.createElement("span");
    balloon.className = "balloon";
    const depth = i % 3;
    // Distribución por franjas para que no se amontonen al azar.
    balloon.style.left = `${5 + ((i + Math.random() * .55) / count) * 90}%`;
    balloon.style.setProperty("--balloon-width", `${48 + depth * 10 + Math.random() * 8}px`);
    balloon.style.setProperty("--balloon-opacity", String(.7 + depth * .12));
    balloon.style.setProperty("--balloon-duration", `${8.5 + (2 - depth) * 1.1 + Math.random() * 1.5}s`);
    balloon.style.setProperty("--balloon-delay", `${Math.random() * 3.2}s`);
    balloon.style.setProperty("--balloon-drift", `${(Math.random() - .5) * 100}px`);
    balloon.style.setProperty("--balloon-sway", `${3.5 + Math.random() * 1.5}s`);
    balloon.style.setProperty("--balloon-phase", `${-Math.random() * 4}s`);
    balloon.style.zIndex = String(depth);
    const art = document.createElement("span");
    art.className = "balloon-art";
    art.innerHTML = balloonShapes[i % balloonShapes.length];
    balloon.appendChild(art);
    balloon.addEventListener("animationend", (event) => {
      if (event.target === balloon) balloon.remove();
    });
    balloons.appendChild(balloon);
  }
  balloonContainer.appendChild(balloons);
}

if (balloonContainer) {
  launchBalloons();
  document.querySelector("[data-birthday-replay]")?.addEventListener("click", launchBalloons);
  reducedMotion.addEventListener("change", () => {
    if (reducedMotion.matches) balloonContainer.replaceChildren();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) balloonContainer.replaceChildren();
  });
}

// Visor de foto de perfil ampliada (1280 px)
const btnAbrirAvatar = document.getElementById("abrir-avatar-ampliado");
const dialogAvatar = document.getElementById("dialog-avatar-ampliado");
const btnCerrarAvatar = document.getElementById("cerrar-avatar-ampliado");
const imgAvatarAmpliada = document.getElementById("img-avatar-ampliado");

if (btnAbrirAvatar && dialogAvatar && btnCerrarAvatar && imgAvatarAmpliada) {
  btnAbrirAvatar.addEventListener("click", () => {
    if (!imgAvatarAmpliada.getAttribute("src")) {
      imgAvatarAmpliada.src = btnAbrirAvatar.dataset.fullSrc;
    }
    dialogAvatar.showModal();
  });

  btnCerrarAvatar.addEventListener("click", () => dialogAvatar.close());
  dialogAvatar.addEventListener("click", (event) => {
    if (event.target === dialogAvatar) dialogAvatar.close();
  });
}

// Vista previa, encuadre circular y zoom antes de subir la foto
const avatarForm = document.querySelector("#cambiar-avatar form[enctype='multipart/form-data']");
const avatarInput = document.getElementById("avatar-file");
const avatarBox = document.getElementById("avatar-cropper-box");
const avatarCanvas = document.getElementById("avatar-crop-canvas");
const avatarZoom = document.getElementById("avatar-zoom-range");

if (avatarForm && avatarInput && avatarBox && avatarCanvas && avatarZoom) {
  const ctx = avatarCanvas.getContext("2d");
  let img = null;
  let scale = 1;
  let minScale = 1;
  let offsetX = 0;
  let offsetY = 0;
  let dragging = false;
  let startX = 0;
  let startY = 0;

  const clampOffsets = () => {
    const w = img.width * scale;
    const h = img.height * scale;
    if (w <= avatarCanvas.width) {
      offsetX = (avatarCanvas.width - w) / 2;
    } else {
      offsetX = Math.min(0, Math.max(avatarCanvas.width - w, offsetX));
    }
    if (h <= avatarCanvas.height) {
      offsetY = (avatarCanvas.height - h) / 2;
    } else {
      offsetY = Math.min(0, Math.max(avatarCanvas.height - h, offsetY));
    }
  };


  const drawCropper = () => {
    if (!img) return;
    ctx.clearRect(0, 0, avatarCanvas.width, avatarCanvas.height);
    ctx.drawImage(img, offsetX, offsetY, img.width * scale, img.height * scale);
  };

  const cargarImagenEnRecortador = (url, revocarAlCargar) => {
    const loaded = new Image();
    loaded.onload = () => {
      if (revocarAlCargar) URL.revokeObjectURL(url);
      img = loaded;
      minScale = Math.max(avatarCanvas.width / img.width, avatarCanvas.height / img.height);
      scale = minScale;
      avatarZoom.value = "1";
      offsetX = (avatarCanvas.width - img.width * scale) / 2;
      offsetY = (avatarCanvas.height - img.height * scale) / 2;
      avatarBox.hidden = false;
      avatarBox.style.display = "flex";
      drawCropper();
    };
    loaded.onerror = () => {
      if (revocarAlCargar) URL.revokeObjectURL(url);
      avatarBox.hidden = true;
      avatarBox.style.display = "none";
      img = null;
    };
    loaded.src = url;
  };

  const btnEditarActual = document.getElementById("editar-avatar-actual");
  if (btnEditarActual) {
    btnEditarActual.addEventListener("click", () => {
      cargarImagenEnRecortador(btnEditarActual.dataset.avatarSrc, false);
      avatarBox.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }

  avatarInput.addEventListener("change", () => {
    const file = avatarInput.files ? avatarInput.files.item(0) : null;
    if (!file || !file.type.startsWith("image/")) {
      avatarBox.hidden = true;
      avatarBox.style.display = "none";
      img = null;
      return;
    }
    cargarImagenEnRecortador(URL.createObjectURL(file), true);
  });

  avatarZoom.addEventListener("input", () => {
    if (!img) return;
    const prevScale = scale;
    scale = minScale * parseFloat(avatarZoom.value);
    const cx = avatarCanvas.width / 2;
    const cy = avatarCanvas.height / 2;
    offsetX = cx - ((cx - offsetX) / prevScale) * scale;
    offsetY = cy - ((cy - offsetY) / prevScale) * scale;
    clampOffsets();
    drawCropper();
  });

  avatarCanvas.addEventListener("pointerdown", (e) => {
    if (!img) return;
    dragging = true;
    startX = e.clientX - offsetX;
    startY = e.clientY - offsetY;
    avatarCanvas.setPointerCapture(e.pointerId);
  });

  avatarCanvas.addEventListener("pointermove", (e) => {
    if (!dragging || !img) return;
    offsetX = e.clientX - startX;
    offsetY = e.clientY - startY;
    clampOffsets();
    drawCropper();
  });

  avatarCanvas.addEventListener("pointerup", () => {
    dragging = false;
  });

  avatarForm.addEventListener("submit", (e) => {
    if (!img) return;
    e.preventDefault();
    const out = document.createElement("canvas");
    out.width = 1280;
    out.height = 1280;
    const octx = out.getContext("2d");
    const factor = out.width / avatarCanvas.width;
    octx.drawImage(
      img,
      offsetX * factor,
      offsetY * factor,
      img.width * scale * factor,
      img.height * scale * factor
    );
    out.toBlob(
      (blob) => {
        if (!blob) {
          avatarForm.submit();
          return;
        }
        const dt = new DataTransfer();
        dt.items.add(new File([blob], "avatar.webp", { type: "image/webp" }));
        avatarInput.files = dt.files;
        avatarForm.submit();
      },
      "image/webp",
      0.92
    );
  });
}


