document.addEventListener('DOMContentLoaded', () => {
  const tooltip = document.getElementById('day-tooltip');
  let justDragged = false;

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
      if (justDragged) return;
      const dialog = document.getElementById('modal-' + cell.dataset.date);
      if (dialog && typeof dialog.showModal === 'function') {
        dialog.showModal();
      }
    });

    // --- Przeciąganie dnia na dzień: kopiuje moją dostępność (status + godziny) ---
    cell.addEventListener('dragstart', (e) => {
      if (!cell.dataset.date || !cell.getAttribute('draggable')) return;
      e.dataTransfer.effectAllowed = 'copy';
      e.dataTransfer.setData('text/plain', cell.dataset.date);
      cell.classList.add('is-dragging');
    });

    cell.addEventListener('dragend', () => {
      cell.classList.remove('is-dragging');
      document.querySelectorAll('.day-cell.drag-over').forEach(c => c.classList.remove('drag-over'));
    });

    cell.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
      cell.classList.add('drag-over');
    });

    cell.addEventListener('dragleave', () => {
      cell.classList.remove('drag-over');
    });

    cell.addEventListener('drop', async (e) => {
      e.preventDefault();
      cell.classList.remove('drag-over');

      const sourceDate = e.dataTransfer.getData('text/plain');
      const targetDate = cell.dataset.date;
      if (!sourceDate || sourceDate === targetDate) return;

      justDragged = true;
      setTimeout(() => { justDragged = false; }, 300);

      try {
        const res = await fetch(window.COPY_AVAILABILITY_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source_date: sourceDate, target_date: targetDate }),
        });
        const result = await res.json().catch(() => ({}));

        if (res.ok && result.ok) {
          location.hash = '#day-' + targetDate;
          location.reload();
        } else {
          showDragToast(result.message || 'Nie udało się skopiować dostępności.', true);
        }
      } catch (err) {
        showDragToast('Błąd połączenia z serwerem.', true);
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

function showDragToast(message, isError) {
  let toast = document.getElementById('drag-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'drag-toast';
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.className = 'drag-toast' + (isError ? ' drag-toast-error' : '');
  toast.style.display = 'block';
  clearTimeout(toast._hideTimer);
  toast._hideTimer = setTimeout(() => { toast.style.display = 'none'; }, 3500);
}

function toggleHours(radio) {
  const row = radio.closest('form').querySelector('.hours-row');
  if (!row) return;
  row.style.display = radio.value === 'available' ? 'flex' : 'none';
}
