// Auto-hide flash messages
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.flash').forEach((el, i) => {
    setTimeout(() => {
      el.classList.add('flash-hide');
      setTimeout(() => el.remove(), 400);
    }, 4000 + i * 300);
  });
});

function copyText(elId) {
  const el = document.getElementById(elId);
  const text = el.tagName === 'INPUT' ? el.value : el.textContent.trim();
  navigator.clipboard.writeText(text).then(() => {
    const original = el.tagName === 'INPUT' ? null : el.textContent;
    if (!original) return;
    el.textContent = 'Skopiowano!';
    setTimeout(() => { el.textContent = original; }, 1200);
  }).catch(() => {
    if (el.tagName === 'INPUT') { el.select(); document.execCommand('copy'); }
  });
}
