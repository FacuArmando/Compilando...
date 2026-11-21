"use strict";

const theater = document.querySelector("[data-bday-theater]");
if (theater) {
  const stage = theater.querySelector("[data-bday-stage]");
  const terminal = theater.querySelector("[data-bday-terminal]");
  const bootScreen = theater.querySelector("[data-ubuntu-boot]");
  const loginScreen = theater.querySelector("[data-ubuntu-login]");
  const passEl = theater.querySelector("[data-ubuntu-pass]");
  const desktopView = theater.querySelector("[data-ubuntu-desktop]");
  const powerMenu = theater.querySelector("[data-ubuntu-power]");
  const shutdownScreen = theater.querySelector("[data-ubuntu-shutdown]");
  const partyBox = theater.querySelector("[data-bday-party]");
  const balloonLayer = theater.querySelector("[data-dev-bday-balloons]");
  const replayBtn = theater.querySelector("[data-bday-replay]");
  const typedEl = theater.querySelector("[data-bday-typed]");
  const glowEl = theater.querySelector("[data-bday-glow]");
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");

  function getActiveLang() {
    const htmlLang = (document.documentElement.lang || "").toLowerCase();
    const stored = (localStorage.getItem("lang") || localStorage.getItem("locale") || "").toLowerCase();
    return htmlLang.startsWith("en") || stored.startsWith("en") ? "en" : "es";
  }

  function getCodeLine() {
    if (getActiveLang() === "en") {
      return theater.dataset.bdayCodeEn || theater.dataset.bdayCode || 'printf("Happy birthday!\\n");';
    }
    return theater.dataset.bdayCodeEs || theater.dataset.bdayCode || 'printf("¡Feliz cumpleaños!\\n");';
  }

  function getGreetingText() {
    if (getActiveLang() === "en") {
      return theater.dataset.bdayGreetingEn || theater.dataset.bdayGreeting || "HAPPY BIRTHDAY!";
    }
    return theater.dataset.bdayGreetingEs || theater.dataset.bdayGreeting || "¡FELIZ CUMPLEAÑOS!";
  }

  const balloonShapes = [
    `<svg viewBox="0 0 64 78"><ellipse cx="32" cy="36" rx="22" ry="28" fill="#1e293b"/><ellipse cx="32" cy="41" rx="14" ry="19" fill="#f8fafc"/><circle cx="26" cy="24" r="3" fill="#fff"/><circle cx="38" cy="24" r="3" fill="#fff"/><circle cx="27" cy="24" r="1.5" fill="#0f172a"/><circle cx="37" cy="24" r="1.5" fill="#0f172a"/><polygon points="27,30 37,30 32,36" fill="#f59e0b"/><ellipse cx="22" cy="62" rx="7" ry="4" fill="#f59e0b"/><ellipse cx="42" cy="62" rx="7" ry="4" fill="#f59e0b"/><line x1="32" y1="64" x2="32" y2="78" stroke="#94a3b8" stroke-width="1.5"/></svg>`,
    `<svg viewBox="0 0 64 78"><rect x="10" y="14" width="44" height="30" rx="5" fill="#2563eb"/><rect x="14" y="18" width="36" height="22" rx="2" fill="#0f172a"/><text x="32" y="33" text-anchor="middle" fill="#38bdf8" font-family="monospace" font-size="11" font-weight="bold">&gt;_</text><path d="M 4 44 L 60 44 L 55 51 L 9 51 Z" fill="#64748b"/><line x1="32" y1="51" x2="32" y2="78" stroke="#94a3b8" stroke-width="1.5"/></svg>`,
    `<svg viewBox="0 0 64 78"><ellipse cx="32" cy="30" rx="24" ry="27" fill="#10b981"/><polygon points="28,56 36,56 32,62" fill="#10b981"/><text x="32" y="35" text-anchor="middle" fill="#ffffff" font-family="monospace" font-size="15" font-weight="bold">&lt;/&gt;</text><line x1="32" y1="62" x2="32" y2="78" stroke="#94a3b8" stroke-width="1.5"/></svg>`,
    `<svg viewBox="0 0 64 78"><ellipse cx="32" cy="30" rx="24" ry="27" fill="#8b5cf6"/><polygon points="28,56 36,56 32,62" fill="#8b5cf6"/><text x="32" y="35" text-anchor="middle" fill="#ffffff" font-family="monospace" font-size="17" font-weight="bold">{ }</text><line x1="32" y1="62" x2="32" y2="78" stroke="#94a3b8" stroke-width="1.5"/></svg>`,
    `<svg viewBox="0 0 64 78"><ellipse cx="32" cy="30" rx="24" ry="27" fill="#f59e0b"/><polygon points="28,56 36,56 32,62" fill="#f59e0b"/><text x="32" y="36" text-anchor="middle" fill="#ffffff" font-family="monospace" font-size="14" font-weight="bold">0101</text><line x1="32" y1="62" x2="32" y2="78" stroke="#94a3b8" stroke-width="1.5"/></svg>`
  ];

  let timers = [];
  let intervals = [];

  function clearAll() {
    timers.forEach((id) => clearTimeout(id));
    timers = [];
    intervals.forEach((id) => clearInterval(id));
    intervals = [];
  }

  function typeText(el, text, speed) {
    if (!el) return;
    el.textContent = "";
    let idx = 0;
    const id = setInterval(() => {
      idx += 1;
      el.textContent = text.slice(0, idx);
      if (idx >= text.length) clearInterval(id);
    }, speed);
    intervals.push(id);
  }

  function lightUpGreetingInTerminal() {
    if (!glowEl) return;
    glowEl.replaceChildren();
    [...getGreetingText()].forEach((char, i) => {
      const span = document.createElement("span");
      span.textContent = char === " " ? "\u00A0" : char;
      span.className = "glow-char";
      span.style.animationDelay = `${i * 75}ms`;
      glowEl.appendChild(span);
    });
  }

  function spawnBalloons() {
    if (!balloonLayer || reducedMotion.matches) return;
    balloonLayer.replaceChildren();
    for (let i = 0; i < 28; i++) {
      const item = document.createElement("div");
      item.className = "tech-balloon";
      item.innerHTML = balloonShapes[i % balloonShapes.length];
      item.style.left = `${3 + Math.random() * 90}%`;
      item.style.setProperty("--dur", `${4.8 + Math.random() * 2.4}s`);
      item.style.setProperty("--sway", `${(Math.random() - 0.5) * 70}px`);
      item.style.animationDelay = `${Math.random() * 1.4}s`;
      balloonLayer.appendChild(item);
    }
  }

  function runStory() {
    clearAll();
    if (!stage) return;

    if (reducedMotion.matches) {
      stage.hidden = true;
      if (replayBtn) replayBtn.hidden = false;
      return;
    }

    stage.hidden = false;
    if (terminal) {
      terminal.hidden = true;
      terminal.className = "bday-ubuntu-desktop";
    }
    if (bootScreen) bootScreen.hidden = false;
    if (loginScreen) loginScreen.hidden = true;
    if (desktopView) desktopView.hidden = true;
    if (powerMenu) powerMenu.hidden = true;
    if (shutdownScreen) shutdownScreen.hidden = true;
    if (partyBox) partyBox.hidden = true;
    if (replayBtn) replayBtn.hidden = true;
    if (typedEl) typedEl.textContent = "";
    if (passEl) passEl.textContent = "";
    glowEl?.replaceChildren();
    balloonLayer?.replaceChildren();

    stage.className = "bday-floor phase-scene-1";

    timers.push(setTimeout(() => {
      stage.className = "bday-floor phase-scene-2";
    }, 4200));

    timers.push(setTimeout(() => {
      stage.className = "bday-floor phase-scene-3";
    }, 8000));

    timers.push(setTimeout(() => {
      stage.className = "bday-floor phase-scene-4-open";
    }, 11400));

    timers.push(setTimeout(() => {
      stage.className = "bday-floor phase-scene-4";
      if (terminal) {
        terminal.hidden = false;
        terminal.className = "bday-ubuntu-desktop";
      }
      if (bootScreen) bootScreen.hidden = false;
      if (loginScreen) loginScreen.hidden = true;
      if (desktopView) desktopView.hidden = true;
    }, 12700));

    timers.push(setTimeout(() => {
      if (bootScreen) bootScreen.hidden = true;
      if (loginScreen) loginScreen.hidden = false;
      typeText(passEl, "••••••••", 120);
    }, 14200));

    timers.push(setTimeout(() => {
      if (loginScreen) loginScreen.hidden = true;
      if (desktopView) desktopView.hidden = false;
      typeText(typedEl, getCodeLine(), 70);
    }, 15800));

    timers.push(setTimeout(() => {
      stage.className = "bday-floor phase-party";
      if (partyBox) partyBox.hidden = false;
      lightUpGreetingInTerminal();
      spawnBalloons();
    }, 18600));

    timers.push(setTimeout(() => {
      if (powerMenu) powerMenu.hidden = false;
    }, 23000));

    timers.push(setTimeout(() => {
      stage.className = "bday-floor phase-shutdown";
      if (powerMenu) powerMenu.hidden = true;
      if (desktopView) desktopView.hidden = true;
      if (shutdownScreen) shutdownScreen.hidden = false;
      terminal?.classList.add("is-shutting-down");
    }, 24200));

    timers.push(setTimeout(() => {
      if (terminal) terminal.hidden = true;
      stage.className = "bday-floor phase-scene-5";
    }, 26000));

    timers.push(setTimeout(() => {
      stage.className = "bday-floor phase-scene-6a";
    }, 29800));

    timers.push(setTimeout(() => {
      stage.className = "bday-floor phase-scene-6b";
    }, 33800));

    timers.push(setTimeout(() => {
      stage.hidden = true;
      balloonLayer?.replaceChildren();
      if (replayBtn) replayBtn.hidden = false;
    }, 38000));
  }

  replayBtn?.addEventListener("click", runStory);
  runStory();
}
