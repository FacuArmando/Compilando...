"use strict";

(() => {
  const footer = document.querySelector(".site-footer");
  if (!footer) return;

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (!reducedMotion.matches && "IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      footer.classList.add("is-revealed");
      observer.disconnect();
    }, { threshold: 0.08 });
    observer.observe(footer);
  }

  footer.querySelector("[data-footer-top]")?.addEventListener("click", (event) => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    window.scrollTo({ top: 0, behavior: reducedMotion.matches ? "instant" : "smooth" });
    document.querySelector(".community-brand")?.focus({ preventScroll: true });
  });

  // Easter egg: exactamente 5 clics en el logo del footer abre el rompecabezas
  const brandLink = footer.querySelector(".site-footer-brand");
  const dialog = document.getElementById("dialog-axolotl-puzzle");
  const board = document.getElementById("axolotl-puzzle-board");
  const previewImg = document.getElementById("axolotl-puzzle-preview");
  const movesCountEl = document.getElementById("puzzle-moves-count");
  const winBanner = document.getElementById("puzzle-win-banner");
  const winMovesEl = document.getElementById("puzzle-win-moves");
  const hintBtn = document.getElementById("btn-pista-puzzle");
  const resetBtn = document.getElementById("btn-reiniciar-puzzle");
  const closeBtn = document.getElementById("btn-cerrar-puzzle");

  if (!brandLink || !dialog || !board) return;

  const GRID = 3;
  const TOTAL = GRID * GRID;
  let clickCount = 0;
  let clickTimer = null;
  let tiles = [];
  let selectedIdx = null;
  let draggedIdx = null;
  let moves = 0;
  let solved = false;
  let sourceImage = null;

  function shuffleTiles() {
    const arr = Array.from({ length: TOTAL }, (_, i) => i);
    do {
      for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [arr[i], arr[j]] = [arr[j], arr[i]];
      }
    } while (arr.every((val, idx) => val === idx));
    return arr;
  }

  function updateMoves() {
    if (movesCountEl) movesCountEl.textContent = String(moves);
  }

  function swapTiles(posA, posB) {
    if (solved || posA === null || posB === null || posA === posB) return;
    [tiles[posA], tiles[posB]] = [tiles[posB], tiles[posA]];
    selectedIdx = null;
    draggedIdx = null;
    moves += 1;
    updateMoves();

    if (tiles.every((val, idx) => val === idx)) {
      solved = true;
      if (winMovesEl) winMovesEl.textContent = String(moves);
      if (winBanner) winBanner.hidden = false;
    }
    renderBoard();
  }

  function renderBoard() {
    if (!sourceImage) return;
    board.replaceChildren();

    const size = Math.min(sourceImage.naturalWidth, sourceImage.naturalHeight);
    const offsetX = (sourceImage.naturalWidth - size) / 2;
    const offsetY = (sourceImage.naturalHeight - size) / 2;
    const tileSrcSize = size / GRID;

    tiles.forEach((originalIdx, currentPos) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "puzzle-tile";
      btn.draggable = !solved;
      if (selectedIdx === currentPos) btn.classList.add("is-selected");
      if (solved) btn.classList.add("is-solved");
      btn.setAttribute("aria-label", `Pieza ${currentPos + 1}`);

      const canvas = document.createElement("canvas");
      canvas.width = 240;
      canvas.height = 240;
      const ctx = canvas.getContext("2d");

      const srcCol = originalIdx % GRID;
      const srcRow = Math.floor(originalIdx / GRID);
      ctx.drawImage(
        sourceImage,
        offsetX + srcCol * tileSrcSize,
        offsetY + srcRow * tileSrcSize,
        tileSrcSize,
        tileSrcSize,
        0,
        0,
        canvas.width,
        canvas.height
      );

      btn.appendChild(canvas);

      // Arrastrar y soltar con el mouse
      btn.addEventListener("dragstart", (event) => {
        if (solved) {
          event.preventDefault();
          return;
        }
        draggedIdx = currentPos;
        selectedIdx = null;
        btn.classList.add("is-dragging");
        if (event.dataTransfer) {
          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData("text/plain", String(currentPos));
        }
      });

      btn.addEventListener("dragend", () => {
        btn.classList.remove("is-dragging");
        board.querySelectorAll(".is-drag-over").forEach((el) => el.classList.remove("is-drag-over"));
      });

      btn.addEventListener("dragover", (event) => {
        if (solved || draggedIdx === null || draggedIdx === currentPos) return;
        event.preventDefault();
        btn.classList.add("is-drag-over");
      });

      btn.addEventListener("dragleave", () => {
        btn.classList.remove("is-drag-over");
      });

      btn.addEventListener("drop", (event) => {
        event.preventDefault();
        btn.classList.remove("is-drag-over");
        if (draggedIdx !== null && draggedIdx !== currentPos) {
          swapTiles(draggedIdx, currentPos);
        }
      });

      // También soporta clic en dos fichas (útil en táctil o trackpad)
      btn.addEventListener("click", () => {
        if (solved) return;
        if (selectedIdx === null) {
          selectedIdx = currentPos;
          renderBoard();
        } else if (selectedIdx === currentPos) {
          selectedIdx = null;
          renderBoard();
        } else {
          swapTiles(selectedIdx, currentPos);
        }
      });

      board.appendChild(btn);
    });
  }

  function startNewGame() {
    tiles = shuffleTiles();
    selectedIdx = null;
    draggedIdx = null;
    moves = 0;
    solved = false;
    if (winBanner) winBanner.hidden = true;
    if (previewImg) previewImg.hidden = true;
    updateMoves();

    if (sourceImage) {
      renderBoard();
      return;
    }
    const img = new Image();
    img.onload = () => {
      sourceImage = img;
      renderBoard();
    };
    img.src = board.dataset.img;
  }

  // Detección confiable de 5 clics seguidos en el logo del footer
  brandLink.addEventListener("click", (event) => {
    event.preventDefault();
    clickCount += 1;
    clearTimeout(clickTimer);

    if (clickCount >= 5) {
      clickCount = 0;
      startNewGame();
      if (!dialog.open) dialog.showModal();
      return;
    }

    clickTimer = setTimeout(() => {
      const soloUnClic = clickCount === 1;
      clickCount = 0;
      if (soloUnClic) {
        window.location.href = brandLink.href;
      }
    }, 900);
  });

  // Mantener presionado "Ver guía" muestra la imagen completa
  if (hintBtn && previewImg) {
    const showHint = () => { previewImg.hidden = false; };
    const hideHint = () => { previewImg.hidden = true; };
    hintBtn.addEventListener("pointerdown", showHint);
    hintBtn.addEventListener("pointerup", hideHint);
    hintBtn.addEventListener("pointerleave", hideHint);
    hintBtn.addEventListener("pointercancel", hideHint);
  }

  resetBtn?.addEventListener("click", startNewGame);
  closeBtn?.addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
})();
