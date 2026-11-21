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
const colors = ["#2563eb", "#f59e0b", "#10b981", "#ec4899", "#8b5cf6", "#06b6d4"];

function launchBalloons() {
  if (!balloonContainer || reducedMotion.matches) return;
  balloonContainer.replaceChildren();
  for (let i = 0; i < 24; i++) {
    const balloon = document.createElement("span");
    balloon.className = "balloon";
    const color = colors[i % colors.length];
    balloon.style.background = color;
    balloon.style.color = color;
    balloon.style.left = `${4 + Math.random() * 92}%`;
    balloon.style.setProperty("--dur", `${4.2 + Math.random() * 2.5}s`);
    balloon.style.setProperty("--sway", `${(Math.random() - 0.5) * 60}px`);
    balloon.style.animationDelay = `${Math.random() * 1.4}s`;
    balloonContainer.appendChild(balloon);
  }
}

if (balloonContainer) {
  launchBalloons();
  document.querySelector("[data-birthday-replay]")?.addEventListener("click", launchBalloons);
}
