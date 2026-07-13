document.addEventListener('DOMContentLoaded', () => {
  const tooltip = document.getElementById('day-tooltip');

  document.querySelectorAll('.day-cell').forEach(cell => {
    cell.addEventListener('mousemove', (e) => {
      const offsetX = 18;
      const offsetY = 18;
      let left = e.clientX + offsetX;
      let top = e.clientY + offsetY;
      const maxLeft = window.innerWidth - 300;
      if (left > maxLeft) left = e.clientX - 300 - 10;
      tooltip.style.left = left + 'px';
      tooltip.style.top = top + 'px';
    });

    cell.addEventListener('mouseenter', () => {
      const content = cell.querySelector('.tooltip-content');
      if (content) {
        tooltip.innerHTML = content.innerHTML;
        tooltip.style.display = 'block';
      }
    });

    cell.addEventListener('mouseleave', () => {
      tooltip.style.display = 'none';
    });

    cell.addEventListener('click', () => {
      const dialog = document.getElementById('modal-' + cell.dataset.date);
      if (dialog && typeof dialog.showModal === 'function') {
        dialog.showModal();
      }
    });
  });

  document.querySelectorAll('.day-modal').forEach(dialog => {
    dialog.addEventListener('click', (e) => {
      const rect = dialog.getBoundingClientRect();
      const inDialog = (
        e.clientX >= rect.left && e.clientX <= rect.right &&
        e.clientY >= rect.top && e.clientY <= rect.bottom
      );
      if (!inDialog) dialog.close();
    });

    // toggle hours visibility on load based on current status
    const radios = dialog.querySelectorAll('input[name="status"]');
    radios.forEach(r => { if (r.checked) toggleHours(r); });
  });

  // If URL has #day-YYYY-MM-DD, scroll to it
  if (location.hash && location.hash.startsWith('#day-')) {
    const el = document.querySelector(location.hash);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
});

function toggleHours(radio) {
  const row = radio.closest('form').querySelector('.hours-row');
  if (!row) return;
  row.style.display = radio.value === 'available' ? 'flex' : 'none';
}
