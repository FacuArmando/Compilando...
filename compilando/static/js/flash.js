document.addEventListener('DOMContentLoaded', () => {
  const AUTO_DISMISS_MS = 4000;
  const items = document.querySelectorAll('.flash-message, .flash-messages > div');

  items.forEach((item) => {
    window.setTimeout(() => {
      item.style.transition = 'opacity 260ms ease, transform 260ms ease';
      item.style.opacity = '0';
      item.style.transform = 'translateY(-8px)';

      window.setTimeout(() => {
        item.remove();
        const wrapper = document.querySelector('.flash-messages');
        if (wrapper && wrapper.children.length === 0) {
          wrapper.remove();
        }
      }, 280);
    }, AUTO_DISMISS_MS);
  });

  document.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      const msg = form.getAttribute('data-confirm');
      if (msg && !window.confirm(msg)) {
        event.preventDefault();
      }
    });
  });
});