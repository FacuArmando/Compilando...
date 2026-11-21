/* Una escena local de texto. Nunca lee los campos del formulario ni ejecuta Java. */
(() => {
  const snippets = [
    {
      file: 'Idea.java',
      code: 'interface Idea {\n    String share();\n}\n\nrecord Question(String text)\n        implements Idea {\n    public String share() {\n        return text;\n    }\n}',
    },
    {
      file: 'Community.java',
      code: 'import java.util.List;\n\nclass Community {\n    public static void main(String[] args) {\n        var ideas = List.of(\n            "ask", "share",\n            "learn"\n        );\n        ideas.forEach(System.out::println);\n    }\n}',
    },
    {
      file: 'Developer.java',
      code: 'abstract class Person {\n    abstract String contribute();\n}\n\nclass Developer extends Person {\n    @Override\n    String contribute() {\n        return "A new idea.";\n    }\n}',
    },
    {
      file: 'Learning.java',
      code: 'import java.util.stream.Stream;\n\nclass Learning {\n    public static void main(String[] args) {\n        Stream.of("ideas", "code")\n            .map(String::toUpperCase)\n            .forEach(System.out::println);\n    }\n}',
    },
  ];
  const keywords = new Set('abstract class extends implements import interface new public record return static var void'.split(' '));
  const types = new Set('Community Developer Idea Learning List Person Question Stream String System'.split(' '));
  const tokenPattern = /\/\/[^\n]*|"(?:\\.|[^"\\])*"?|\b[A-Za-z_]\w*\b|\b\d+\b/g;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const wideScreen = window.matchMedia('(min-width: 761px)');

  function paint(node, text, binary) {
    if (binary) {
      node.textContent = text;
      return;
    }
    const fragment = document.createDocumentFragment();
    let offset = 0;
    for (const match of text.matchAll(tokenPattern)) {
      fragment.append(document.createTextNode(text.slice(offset, match.index)));
      const word = match[0];
      const kind = word.startsWith('//') ? 'comment'
        : word.startsWith('"') ? 'string'
          : keywords.has(word) ? 'keyword'
            : types.has(word) ? 'type'
              : /^\d+$/.test(word) ? 'number' : null;
      if (kind) {
        const span = document.createElement('span');
        span.className = `auth-code-${kind}`;
        span.textContent = word;
        fragment.append(span);
      } else {
        fragment.append(document.createTextNode(word));
      }
      offset = match.index + word.length;
    }
    fragment.append(document.createTextNode(text.slice(offset)));
    node.replaceChildren(fragment);
  }

  // Una ventana de bytes UTF-8 del mismo fragmento, agrupados de a tres por fila.
  function toBinary(text) {
    const bytes = Array.from(new TextEncoder().encode(text)).slice(0, 36);
    const rows = [];
    for (let index = 0; index < bytes.length; index += 3) {
      rows.push(bytes.slice(index, index + 3).map(byte => byte.toString(2).padStart(8, '0')).join(' '));
    }
    return rows.join('\n');
  }

  document.querySelectorAll('[data-code-scene]').forEach(scene => {
    const source = scene.querySelector('[data-code-source]');
    const filename = scene.querySelector('[data-code-filename]');
    const status = scene.querySelector('[data-code-status]');
    const encoding = scene.querySelector('[data-code-encoding]');
    const pause = scene.querySelector('[data-code-pause]');
    let index = 0;
    let phase = 'typing';
    let elapsed = 0;
    let nextCharacter = 0;
    let cursor = 0;
    let last = 0;
    let lastPaint = 0;
    let frame = 0;
    let manuallyPaused = false;
    let binary = toBinary(snippets[index].code);

    function setMode(mode) {
      scene.dataset.codeMode = mode;
      encoding.textContent = mode === 'binary' ? 'UTF-8 → 0101' : 'Java · UTF-8';
    }

    function still() {
      phase = 'hold';
      elapsed = 0;
      cursor = snippets[index].code.length;
      setMode('java');
      filename.textContent = snippets[index].file;
      window.I18n.setText(status, 'Una idea en código');
      paint(source, snippets[index].code, false);
    }

    function changePhase(next) {
      phase = next;
      elapsed = 0;
      lastPaint = 0;
      if (next === 'morph') {
        setMode('binary');
        window.I18n.setText(status, 'Cada carácter, una secuencia');
      } else if (next === 'erase') {
        window.I18n.setText(status, 'Otra forma de pensarlo');
      } else if (next === 'typing') {
        index = (index + 1 + Math.floor(Math.random() * (snippets.length - 1))) % snippets.length;
        binary = toBinary(snippets[index].code);
        cursor = 0;
        nextCharacter = 0;
        setMode('java');
        filename.textContent = snippets[index].file;
        window.I18n.setText(status, 'Una idea en código');
      }
    }

    function tick(now) {
      elapsed += Math.min(now - last, 80);
      last = now;
      const code = snippets[index].code;
      if (phase === 'typing') {
        const previous = cursor;
        while (elapsed >= nextCharacter && cursor < code.length) {
          const character = code[cursor++];
          nextCharacter += character === '\n' ? 95 : /[;{}]/.test(character) ? 65 : 12 + Math.random() * 23;
        }
        if (cursor !== previous) paint(source, code.slice(0, cursor), false);
        if (cursor === code.length) changePhase('hold');
      } else if (phase === 'hold' && elapsed > 2300) {
        changePhase('morph');
      } else if (phase === 'morph') {
        if (elapsed > 1600) {
          paint(source, binary, true);
          changePhase('binary');
          window.I18n.setText(status, 'La misma idea, en binario');
        } else if (elapsed - lastPaint > 65) {
          const progress = elapsed / 1600;
          const target = binary.split('\n');
          const original = code.split('\n');
          const rows = target.map((row, line) => Array.from(row, (character, column) => {
            const arrival = (line * row.length + column) / binary.length;
            if (progress > arrival + .15) return character;
            if (progress > arrival - .2) return character === ' ' ? ' ' : Math.random() > .5 ? '1' : '0';
            return original[line]?.[column] || ' ';
          }).join(''));
          paint(source, rows.join('\n'), true);
          lastPaint = elapsed;
        }
      } else if (phase === 'binary' && elapsed > 1700) {
        changePhase('erase');
      } else if (phase === 'erase') {
        const remaining = Math.max(0, binary.length - Math.floor(elapsed / 3));
        if (elapsed - lastPaint > 30) {
          paint(source, binary.slice(0, remaining), true);
          lastPaint = elapsed;
        }
        if (remaining === 0) changePhase('typing');
      }
      frame = window.requestAnimationFrame(tick);
    }

    function sync() {
      window.cancelAnimationFrame(frame);
      frame = 0;
      if (reducedMotion.matches) still();
      pause.hidden = reducedMotion.matches;
      const running = !reducedMotion.matches && wideScreen.matches && !document.hidden && !manuallyPaused;
      scene.dataset.codeRunning = String(running);
      if (running) {
        last = performance.now();
        frame = window.requestAnimationFrame(tick);
      }
    }

    pause.addEventListener('click', () => {
      manuallyPaused = !manuallyPaused;
      pause.setAttribute('aria-pressed', String(manuallyPaused));
      window.I18n.setAttribute(pause, 'aria-label', manuallyPaused ? 'Reanudar animación de código' : 'Pausar animación de código');
      sync();
    });
    reducedMotion.addEventListener('change', sync);
    wideScreen.addEventListener('change', sync);
    document.addEventListener('visibilitychange', sync);
    window.addEventListener('pagehide', () => {
      window.cancelAnimationFrame(frame);
      scene.dataset.codeRunning = 'false';
    });
    window.addEventListener('pageshow', sync);
    paint(source, snippets[index].code, false);
    sync();
  });
})();
