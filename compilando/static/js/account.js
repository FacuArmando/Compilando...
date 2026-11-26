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

  const duration = 250;
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

// Conservar los números que ya envió el servidor: no reiniciarlos a cero al abrir.
document.querySelectorAll("[data-count-target]").forEach((el) => {
  const target = Number(el.dataset.countTarget) || 0;
  el.dataset.currentValue = String(target);
});

// Actualización automática en segundo plano (al volver a la pestaña o cada 15s)
const statsSection = document.querySelector("[data-stats-url]");
if (statsSection) {
  const statsUrl = statsSection.dataset.statsUrl;
  const ringEl = statsSection.querySelector("[data-ring-progress]");
  const ratioEl = statsSection.querySelector("[data-stat-ratio]");
  const refreshInterval = 30000;
  let refreshPending = false;
  let lastRefresh = Date.now(); // El HTML inicial ya incluye las estadísticas.

  const refreshStats = async (event) => {
    const restored = event && event.type === "pageshow" && event.persisted;
    if (document.hidden || refreshPending || (!restored && Date.now() - lastRefresh < refreshInterval)) return;
    refreshPending = true;
    lastRefresh = Date.now();
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
    } finally {
      refreshPending = false;
    }
  };

  document.addEventListener("visibilitychange", refreshStats);
  window.addEventListener("pageshow", refreshStats);
  setInterval(refreshStats, refreshInterval);
}

// Globos festivos cuando es el cumpleaños del usuario
const balloonContainer = document.querySelector("[data-birthday-balloons]");
const balloonPalettes = [
  ["#c9d6ff", "#7695eb", "#344f9e"],
  ["#eadcff", "#b598e2", "#705194"],
  ["#b9efe6", "#61bdaf", "#286f72"],
  ["#fff1cf", "#e0bb79", "#9b703d"],
  ["#f9ddeb", "#d79bb8", "#935772"],
];
let balloonLaunch = 0;

function createBalloonArt(id, [light, color, shade]) {
  // Solo formas y colores locales: no se inserta contenido del usuario.
  return `<svg viewBox="0 0 100 210" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">
    <defs>
      <radialGradient id="${id}-body" cx="32%" cy="26%" r="76%">
        <stop stop-color="${light}"/>
        <stop offset=".48" stop-color="${color}"/>
        <stop offset="1" stop-color="${shade}"/>
      </radialGradient>
      <radialGradient id="${id}-shine" cx="30%" cy="24%" r="65%">
        <stop stop-color="#fff" stop-opacity=".75"/>
        <stop offset="1" stop-color="#fff" stop-opacity="0"/>
      </radialGradient>
      <linearGradient id="${id}-ribbon" x1="0" y1="0" x2="1" y2="1">
        <stop stop-color="${light}" stop-opacity=".85"/>
        <stop offset="1" stop-color="${color}" stop-opacity=".18"/>
      </linearGradient>
    </defs>
    <path class="balloon-ribbon" d="M50 113 C31 137 69 144 51 166 S35 192 47 205"
      fill="none" stroke="url(#${id}-ribbon)" stroke-width="1.2" stroke-linecap="round"/>
    <path d="M47 106 L43 115 Q50 112 57 115 L53 106Z" fill="${shade}"/>
    <path d="M50 8 C27 8 11 27 11 51 C11 77 32 100 50 109 C68 100 89 77 89 51 C89 27 73 8 50 8Z"
      fill="url(#${id}-body)" stroke="${light}" stroke-opacity=".32" stroke-width=".7"/>
    <ellipse cx="32" cy="33" rx="10" ry="17" transform="rotate(28 32 33)" fill="url(#${id}-shine)"/>
    <path d="M21 55 C18 36 28 19 43 16" fill="none" stroke="#fff" stroke-opacity=".48" stroke-width="1.4" stroke-linecap="round"/>
    <path d="M66 88 C77 77 83 65 83 53" fill="none" stroke="${light}" stroke-opacity=".23" stroke-width="1.2" stroke-linecap="round"/>
    <path d="M46 108 Q50 110 54 108" fill="none" stroke="${light}" stroke-opacity=".65" stroke-width="1.2"/>
  </svg>`;
}

function launchBalloons() {
  if (!balloonContainer) return;
  balloonContainer.replaceChildren();
  if (reducedMotion.matches) return;

  const count = window.innerWidth < 720 ? 8 : 15;
  const launch = ++balloonLaunch;
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
    balloon.style.setProperty("--balloon-delay", `${Math.random() * 1.8}s`);
    balloon.style.setProperty("--balloon-drift", `${(Math.random() - .5) * 100}px`);
    balloon.style.setProperty("--balloon-sway", `${3.5 + Math.random() * 1.5}s`);
    balloon.style.setProperty("--balloon-phase", `${-Math.random() * 4}s`);
    balloon.style.zIndex = String(depth);
    const art = document.createElement("span");
    art.className = "balloon-art";
    art.innerHTML = createBalloonArt(`birthday-${launch}-${i}`, balloonPalettes[i % balloonPalettes.length]);
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
