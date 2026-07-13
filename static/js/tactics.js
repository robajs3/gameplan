document.addEventListener('DOMContentLoaded', () => {
  const list = document.getElementById('sortableMaps');
  const form = document.getElementById('prefsForm');
  if (!list || !form) return;

  let dragEl = null;

  list.querySelectorAll('.sortable-item').forEach(item => {
    item.addEventListener('dragstart', () => {
      dragEl = item;
      item.classList.add('dragging');
    });
    item.addEventListener('dragend', () => {
      item.classList.remove('dragging');
      renumber();
    });
  });

  list.addEventListener('dragover', (e) => {
    e.preventDefault();
    const after = getDragAfterElement(list, e.clientY);
    if (!dragEl) return;
    if (after == null) {
      list.appendChild(dragEl);
    } else {
      list.insertBefore(dragEl, after);
    }
  });

  function getDragAfterElement(container, y) {
    const items = [...container.querySelectorAll('.sortable-item:not(.dragging)')];
    return items.reduce((closest, child) => {
      const box = child.getBoundingClientRect();
      const offset = y - box.top - box.height / 2;
      if (offset < 0 && offset > closest.offset) {
        return { offset, element: child };
      } else {
        return closest;
      }
    }, { offset: -Infinity }).element;
  }

  function renumber() {
    const items = list.querySelectorAll('.sortable-item');
    items.forEach((item, idx) => {
      const pts = items.length - 1 - idx;
      item.querySelector('.sortable-points').textContent = pts;
    });
  }

  form.addEventListener('submit', () => {
    const wrap = document.getElementById('orderInputs');
    wrap.innerHTML = '';
    list.querySelectorAll('.sortable-item').forEach(item => {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'order';
      input.value = item.dataset.id;
      wrap.appendChild(input);
    });
  });

  renumber();
});
