"use strict";

(() => {
  const footer = document.querySelector(".site-footer");
  if (!footer) return;

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (!reducedMotion.matches && "IntersectionObserver" in window) {
    // Sin JavaScript o sin observador, el contenido permanece visible.
    const observer = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      footer.classList.add("is-revealed");
      observer.disconnect();
    }, { threshold: 0.08 });
    observer.observe(footer);
  }

  footer.querySelector("[data-footer-top]").addEventListener("click", (event) => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    window.scrollTo({ top: 0, behavior: reducedMotion.matches ? "instant" : "smooth" });
    document.querySelector(".community-brand")?.focus({ preventScroll: true });
  });
})();
