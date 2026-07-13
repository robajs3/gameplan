document.addEventListener('DOMContentLoaded', () => {
  const cfg = window.GAMEPLAN_BOARD;
  const wrap = document.getElementById('boardWrap');
  if (!cfg || !wrap) return;

  const canvas = document.getElementById('boardCanvas');
  const ctx = canvas.getContext('2d');
  const objectsLayer = document.getElementById('boardObjects');
  const statusEl = document.getElementById('boardStatus');
  const hintEl = document.getElementById('boardHint');
  const widthInput = document.getElementById('boardWidth');

  const ICONS = {
    player_t: { icon: '', bg: '#ff6a1a', text: '#1a1206' },
    player_ct: { icon: '', bg: '#4da3ff', text: '#0b1522' },
    smoke: { icon: '💨', bg: '#9aa4b5', text: '#12151b' },
    molotov: { icon: '🔥', bg: '#ff7a1a', text: '#1a1206' },
    flash: { icon: '⚡', bg: '#f5c542', text: '#1a1206' },
    he: { icon: '💥', bg: '#ff5470', text: '#1a1206' },
    decoy: { icon: 'D', bg: '#97a1b3', text: '#12151b' },
  };

  let state = {
    strokes: Array.isArray(cfg.initialData?.strokes) ? cfg.initialData.strokes : [],
    objects: Array.isArray(cfg.initialData?.objects) ? cfg.initialData.objects : [],
  };

  let mode = 'select';
  let color = '#ff6a1a';
  let width = 3;
  let pendingAdd = null;
  let undoStack = [];
  let dirty = false;

  // ---------- helpers ----------
  function snapshot() {
    undoStack.push(JSON.stringify(state));
    if (undoStack.length > 40) undoStack.shift();
  }

  function markDirty() {
    dirty = true;
    statusEl.textContent = 'Niezapisane zmiany...';
  }

  function nextPlayerLabel(type) {
    const count = state.objects.filter(o => o.type === type).length;
    return String((count % 5) + 1);
  }

  function resizeCanvas() {
    const rect = wrap.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    redraw();
  }

  function toFrac(clientX, clientY) {
    const rect = wrap.getBoundingClientRect();
    let x = (clientX - rect.left) / rect.width;
    let y = (clientY - rect.top) / rect.height;
    x = Math.max(-0.02, Math.min(1.02, x));
    y = Math.max(-0.02, Math.min(1.02, y));
    return [x, y];
  }

  function drawArrowHead(x1, y1, x2, y2, strokeColor) {
    const angle = Math.atan2(y2 - y1, x2 - x1);
    const size = 12;
    ctx.beginPath();
    ctx.moveTo(x2, y2);
    ctx.lineTo(x2 - size * Math.cos(angle - Math.PI / 6), y2 - size * Math.sin(angle - Math.PI / 6));
    ctx.lineTo(x2 - size * Math.cos(angle + Math.PI / 6), y2 - size * Math.sin(angle + Math.PI / 6));
    ctx.closePath();
    ctx.fillStyle = strokeColor;
    ctx.fill();
  }

  function drawStroke(s) {
    const rect = wrap.getBoundingClientRect();
    const pts = s.points.map(p => [p[0] * rect.width, p[1] * rect.height]);
    if (pts.length < 1) return;
    ctx.strokeStyle = s.color;
    ctx.fillStyle = s.color;
    ctx.lineWidth = s.width;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    if (s.tool === 'pen') {
      ctx.beginPath();
      ctx.moveTo(pts[0][0], pts[0][1]);
      pts.slice(1).forEach(p => ctx.lineTo(p[0], p[1]));
      ctx.stroke();
    } else if (pts.length >= 2) {
      const [x1, y1] = pts[0];
      const [x2, y2] = pts[pts.length - 1];
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
      if (s.tool === 'arrow') drawArrowHead(x1, y1, x2, y2, s.color);
    }
  }

  function redraw() {
    const rect = wrap.getBoundingClientRect();
    ctx.clearRect(0, 0, rect.width, rect.height);
    state.strokes.forEach(drawStroke);
    if (activeStroke) drawStroke(activeStroke);
  }

  function distToSegment(p, a, b) {
    const [px, py] = p, [ax, ay] = a, [bx, by] = b;
    const dx = bx - ax, dy = by - ay;
    const lenSq = dx * dx + dy * dy;
    let t = lenSq === 0 ? 0 : ((px - ax) * dx + (py - ay) * dy) / lenSq;
    t = Math.max(0, Math.min(1, t));
    const cx = ax + t * dx, cy = ay + t * dy;
    return Math.hypot(px - cx, py - cy);
  }

  function eraseNear(fx, fy) {
    const threshold = 0.02;
    for (let i = state.strokes.length - 1; i >= 0; i--) {
      const pts = state.strokes[i].points;
      for (let j = 0; j < pts.length - 1; j++) {
        if (distToSegment([fx, fy], pts[j], pts[j + 1]) < threshold) {
          snapshot();
          state.strokes.splice(i, 1);
          redraw();
          markDirty();
          return;
        }
      }
      if (pts.length === 1 && Math.hypot(pts[0][0] - fx, pts[0][1] - fy) < threshold) {
        snapshot();
        state.strokes.splice(i, 1);
        redraw();
        markDirty();
        return;
      }
    }
  }

  // ---------- object markers (DOM) ----------
  function renderObjects() {
    objectsLayer.innerHTML = '';
    state.objects.forEach(obj => {
      const meta = ICONS[obj.type] || ICONS.decoy;
      const el = document.createElement('div');
      el.className = 'board-obj';
      el.style.left = (obj.x * 100) + '%';
      el.style.top = (obj.y * 100) + '%';
      el.style.background = meta.bg;
      el.style.color = meta.text;
      el.dataset.id = obj.id;

      const isPlayer = obj.type === 'player_t' || obj.type === 'player_ct';
      el.textContent = isPlayer ? obj.label : meta.icon;
      if (isPlayer) el.classList.add('board-obj-player');

      const del = document.createElement('button');
      del.type = 'button';
      del.className = 'board-obj-del';
      del.textContent = '✕';
      del.addEventListener('pointerdown', (e) => e.stopPropagation());
      del.addEventListener('click', (e) => {
        e.stopPropagation();
        snapshot();
        state.objects = state.objects.filter(o => o.id !== obj.id);
        renderObjects();
        markDirty();
      });
      el.appendChild(del);

      el.addEventListener('pointerdown', (e) => {
        if (mode !== 'select') return;
        e.preventDefault();
        el.setPointerCapture(e.pointerId);
        let moved = false;
        const onMove = (ev) => {
          moved = true;
          const [fx, fy] = toFrac(ev.clientX, ev.clientY);
          obj.x = fx; obj.y = fy;
          el.style.left = (fx * 100) + '%';
          el.style.top = (fy * 100) + '%';
        };
        const onUp = () => {
          el.removeEventListener('pointermove', onMove);
          el.removeEventListener('pointerup', onUp);
          if (moved) { snapshot(); markDirty(); }
        };
        snapshot();
        el.addEventListener('pointermove', onMove);
        el.addEventListener('pointerup', onUp);
      });

      objectsLayer.appendChild(el);
    });
  }

  // ---------- drawing interactions ----------
  let activeStroke = null;

  canvas.addEventListener('pointerdown', (e) => {
    const [fx, fy] = toFrac(e.clientX, e.clientY);

    if (pendingAdd) {
      snapshot();
      const type = pendingAdd;
      const obj = {
        id: 'o' + Date.now() + Math.random().toString(36).slice(2, 7),
        type, x: fx, y: fy,
        label: (type === 'player_t' || type === 'player_ct') ? nextPlayerLabel(type) : '',
        color: null,
      };
      state.objects.push(obj);
      renderObjects();
      markDirty();
      disarmAdd();
      return;
    }

    if (mode === 'eraser') {
      eraseNear(fx, fy);
      return;
    }

    if (mode === 'pen' || mode === 'line' || mode === 'arrow') {
      canvas.setPointerCapture(e.pointerId);
      activeStroke = { tool: mode, color, width, points: [[fx, fy]] };
      redraw();
    }
  });

  canvas.addEventListener('pointermove', (e) => {
    if (!activeStroke) return;
    const [fx, fy] = toFrac(e.clientX, e.clientY);
    if (activeStroke.tool === 'pen') {
      activeStroke.points.push([fx, fy]);
    } else {
      activeStroke.points[1] = [fx, fy];
    }
    redraw();
  });

  function endStroke() {
    if (!activeStroke) return;
    if (activeStroke.points.length > (activeStroke.tool === 'pen' ? 1 : 1)) {
      snapshot();
      state.strokes.push(activeStroke);
      markDirty();
    }
    activeStroke = null;
    redraw();
  }
  canvas.addEventListener('pointerup', endStroke);
  canvas.addEventListener('pointerleave', () => { if (activeStroke) endStroke(); });

  // ---------- toolbar ----------
  function disarmAdd() {
    pendingAdd = null;
    document.querySelectorAll('.board-add').forEach(b => b.classList.remove('active'));
    canvas.classList.remove('board-canvas-armed');
  }

  document.querySelectorAll('[data-mode]').forEach(btn => {
    btn.addEventListener('click', () => {
      mode = btn.dataset.mode;
      disarmAdd();
      document.querySelectorAll('[data-mode]').forEach(b => b.classList.toggle('active', b === btn));
      canvas.classList.toggle('board-canvas-draw', mode !== 'select');
      canvas.style.pointerEvents = 'auto';
      objectsLayer.style.pointerEvents = mode === 'select' ? 'auto' : 'none';
      canvas.style.cursor = mode === 'select' ? 'default' : (mode === 'eraser' ? 'cell' : 'crosshair');
    });
  });

  document.querySelectorAll('.board-color').forEach(btn => {
    btn.addEventListener('click', () => {
      color = btn.dataset.color;
      document.querySelectorAll('.board-color').forEach(b => b.classList.toggle('active', b === btn));
    });
  });

  widthInput.addEventListener('input', () => { width = parseInt(widthInput.value, 10) || 3; });

  document.querySelectorAll('.board-add').forEach(btn => {
    btn.addEventListener('click', () => {
      if (pendingAdd === btn.dataset.add) { disarmAdd(); return; }
      disarmAdd();
      pendingAdd = btn.dataset.add;
      btn.classList.add('active');
      canvas.classList.add('board-canvas-armed');
      // switch underlying interaction layer so clicks land on canvas
      mode = 'select';
      document.querySelectorAll('[data-mode]').forEach(b => b.classList.toggle('active', b.dataset.mode === 'select'));
      canvas.style.pointerEvents = 'auto';
      objectsLayer.style.pointerEvents = 'none';
      canvas.style.cursor = 'copy';
    });
  });

  document.getElementById('boardUndo').addEventListener('click', () => {
    if (!undoStack.length) return;
    state = JSON.parse(undoStack.pop());
    redraw();
    renderObjects();
    markDirty();
  });

  document.getElementById('boardClear').addEventListener('click', async () => {
    if (!confirm('Na pewno wyczyścić całą tablicę? Tej operacji nie można cofnąć po zapisie.')) return;
    snapshot();
    state = { strokes: [], objects: [] };
    redraw();
    renderObjects();
    try {
      const res = await fetch(cfg.resetUrl, { method: 'POST' });
      if (res.ok) {
        dirty = false;
        statusEl.textContent = 'Tablica wyczyszczona.';
      }
    } catch (err) { /* offline — local clear still applied */ }
  });

  document.getElementById('boardSave').addEventListener('click', async () => {
    const saveBtn = document.getElementById('boardSave');
    saveBtn.disabled = true;
    saveBtn.textContent = 'Zapisywanie...';
    try {
      const res = await fetch(cfg.saveUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(state),
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        dirty = false;
        statusEl.textContent = `Zapisano o ${data.updated_at} (${data.updated_by})`;
      } else {
        statusEl.textContent = 'Błąd zapisu tablicy.';
      }
    } catch (err) {
      statusEl.textContent = 'Błąd sieci — nie udało się zapisać.';
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = '💾 Zapisz tablicę';
    }
  });

  window.addEventListener('beforeunload', (e) => {
    if (dirty) { e.preventDefault(); e.returnValue = ''; }
  });

  window.addEventListener('resize', resizeCanvas);

  // init
  objectsLayer.style.pointerEvents = 'auto';
  resizeCanvas();
  renderObjects();
});
