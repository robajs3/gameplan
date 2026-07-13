import os
import json
import uuid
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user

from extensions import db
from models import GameMap, MapPreference, MapTactic, TacticImage, Membership

tactics_bp = Blueprint('tactics', __name__, url_prefix='/tactics')

ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Klucze map, dla których mamy własne (nie-Valve'owe) layouty SVG w
# static/img/maps/<klucz>.svg — patrz templates/tactic_map.html
BOARD_STROKE_TOOLS = {'pen', 'line', 'arrow'}
BOARD_OBJECT_TYPES = {
    'player_t', 'player_ct', 'smoke', 'molotov', 'flash', 'he', 'decoy', 'label', 'skull'
}
BOARD_MAX_STROKES = 400
BOARD_MAX_OBJECTS = 150
BOARD_MAX_POINTS_PER_STROKE = 800


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def _clean_board_payload(raw):
    """Waliduje i sanitizuje JSON przesłany z tablicy taktycznej (canvas)."""
    if not isinstance(raw, dict):
        return None

    strokes_in = raw.get('strokes', [])
    objects_in = raw.get('objects', [])
    if not isinstance(strokes_in, list) or not isinstance(objects_in, list):
        return None
    if len(strokes_in) > BOARD_MAX_STROKES or len(objects_in) > BOARD_MAX_OBJECTS:
        return None

    def _num(v, lo=-0.2, hi=1.2):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        if f != f or f < lo or f > hi:  # NaN check + range
            return None
        return round(f, 5)

    strokes = []
    for s in strokes_in:
        if not isinstance(s, dict):
            continue
        tool = s.get('tool')
        if tool not in BOARD_STROKE_TOOLS:
            continue
        color = s.get('color') if isinstance(s.get('color'), str) else '#ffffff'
        color = color[:20]
        try:
            width = max(1, min(12, int(s.get('width', 3))))
        except (TypeError, ValueError):
            width = 3
        pts_in = s.get('points', [])
        if not isinstance(pts_in, list) or not pts_in:
            continue
        pts = []
        for p in pts_in[:BOARD_MAX_POINTS_PER_STROKE]:
            if not isinstance(p, (list, tuple)) or len(p) != 2:
                continue
            x, y = _num(p[0]), _num(p[1])
            if x is None or y is None:
                continue
            pts.append([x, y])
        if pts:
            strokes.append({'tool': tool, 'color': color, 'width': width, 'points': pts})

    objects = []
    for o in objects_in:
        if not isinstance(o, dict):
            continue
        otype = o.get('type')
        if otype not in BOARD_OBJECT_TYPES:
            continue
        x, y = _num(o.get('x')), _num(o.get('y'))
        if x is None or y is None:
            continue
        label = str(o.get('label', ''))[:12]
        color = o.get('color') if isinstance(o.get('color'), str) else None
        if color:
            color = color[:20]
        objects.append({
            'id': str(o.get('id', uuid.uuid4().hex))[:40],
            'type': otype, 'x': x, 'y': y, 'label': label, 'color': color,
        })

    return {'strokes': strokes, 'objects': objects}


def _require_team():
    if not current_user.membership:
        flash('Najpierw dołącz do drużyny.', 'warning')
        return False
    return True


@tactics_bp.route('/')
@login_required
def index():
    if not _require_team():
        return redirect(url_for('main.team_gate'))

    team = current_user.team
    maps = GameMap.query.order_by(GameMap.id).all()
    prefs = {p.map_id: p.points for p in MapPreference.query.filter_by(user_id=current_user.id).all()}

    members = Membership.query.filter_by(team_id=team.id).all()
    member_ids = [m.user_id for m in members]

    ranking = []
    for m in maps:
        rows = MapPreference.query.filter(
            MapPreference.map_id == m.id, MapPreference.user_id.in_(member_ids)
        ).all()
        total = sum(r.points for r in rows)
        avg = round(total / len(rows), 1) if rows else None
        ranking.append({'map': m, 'total': total, 'avg': avg, 'votes': len(rows)})
    ranking.sort(key=lambda x: x['total'], reverse=True)

    has_prefs = len(prefs) == len(maps)
    my_order = sorted(maps, key=lambda m: -prefs.get(m.id, -1)) if has_prefs else maps

    return render_template(
        'tactics.html', team=team, maps=maps, prefs=prefs,
        ranking=ranking, has_prefs=has_prefs, my_order=my_order
    )


@tactics_bp.route('/preferences', methods=['POST'])
@login_required
def save_preferences():
    if not _require_team():
        return redirect(url_for('main.team_gate'))

    maps = GameMap.query.all()
    order = request.form.getlist('order')
    if len(order) != len(maps):
        flash('Musisz uszeregować wszystkie mapy.', 'danger')
        return redirect(url_for('tactics.index'))

    try:
        order_ids = [int(x) for x in order]
    except ValueError:
        flash('Nieprawidłowe dane.', 'danger')
        return redirect(url_for('tactics.index'))

    n = len(order_ids)
    for idx, map_id in enumerate(order_ids):
        points = n - 1 - idx
        row = MapPreference.query.filter_by(user_id=current_user.id, map_id=map_id).first()
        if not row:
            row = MapPreference(user_id=current_user.id, map_id=map_id, points=points)
            db.session.add(row)
        else:
            row.points = points
    db.session.commit()
    flash('Zapisano Twoje preferencje map.', 'success')
    return redirect(url_for('tactics.index'))


MAP_IMAGE_EXT = 'png'  # placeholder mapy w static/img/maps/<key>.png


def _owned_tactic_or_404(tactic_id):
    """Zwraca taktykę, jeśli należy do drużyny zalogowanego użytkownika, inaczej None."""
    tactic = MapTactic.query.get_or_404(tactic_id)
    if not current_user.team or tactic.team_id != current_user.team.id:
        return None
    return tactic


@tactics_bp.route('/map/<int:map_id>')
@login_required
def map_tactics(map_id):
    """Lista wszystkich taktyk drużyny dla danej mapy — menu wyboru/dodawania."""
    if not _require_team():
        return redirect(url_for('main.team_gate'))

    team = current_user.team
    game_map = GameMap.query.get_or_404(map_id)
    tactics = (
        MapTactic.query.filter_by(team_id=team.id, map_id=map_id)
        .order_by(MapTactic.created_at.asc()).all()
    )
    return render_template('tactics_map_list.html', team=team, map=game_map, tactics=tactics)


@tactics_bp.route('/map/<int:map_id>/new', methods=['POST'])
@login_required
def tactic_new(map_id):
    if not _require_team():
        return redirect(url_for('main.team_gate'))

    team = current_user.team
    GameMap.query.get_or_404(map_id)
    name = (request.form.get('name') or '').strip()[:80] or 'Nowa taktyka'

    tactic = MapTactic(
        team_id=team.id, map_id=map_id, name=name, content='',
        board_data=json.dumps({'strokes': [], 'objects': []}),
        created_by=current_user.id, updated_by=current_user.id,
    )
    db.session.add(tactic)
    db.session.commit()
    flash(f'Dodano taktykę „{name}”.', 'success')
    return redirect(url_for('tactics.tactic_detail', tactic_id=tactic.id))


@tactics_bp.route('/tactic/<int:tactic_id>')
@login_required
def tactic_detail(tactic_id):
    tactic = _owned_tactic_or_404(tactic_id)
    if not tactic:
        flash('Brak dostępu do tej taktyki.', 'danger')
        return redirect(url_for('tactics.index'))

    game_map = GameMap.query.get_or_404(tactic.map_id)
    images = TacticImage.query.filter_by(tactic_id=tactic.id).order_by(TacticImage.uploaded_at.desc()).all()

    board_data = {'strokes': [], 'objects': []}
    if tactic.board_data:
        try:
            board_data = json.loads(tactic.board_data)
        except (ValueError, TypeError):
            board_data = {'strokes': [], 'objects': []}

    return render_template(
        'tactic_editor.html', team=current_user.team, map=game_map, tactic=tactic, images=images,
        board_data=board_data, board_updated_at=tactic.board_updated_at,
        map_image_ext=MAP_IMAGE_EXT,
    )


@tactics_bp.route('/tactic/<int:tactic_id>/rename', methods=['POST'])
@login_required
def tactic_rename(tactic_id):
    tactic = _owned_tactic_or_404(tactic_id)
    if not tactic:
        flash('Brak dostępu do tej taktyki.', 'danger')
        return redirect(url_for('tactics.index'))

    name = (request.form.get('name') or '').strip()[:80]
    if name:
        tactic.name = name
        tactic.updated_by = current_user.id
        db.session.commit()
        flash('Zmieniono nazwę taktyki.', 'success')
    return redirect(url_for('tactics.tactic_detail', tactic_id=tactic.id))


@tactics_bp.route('/tactic/<int:tactic_id>/delete', methods=['POST'])
@login_required
def tactic_delete(tactic_id):
    tactic = _owned_tactic_or_404(tactic_id)
    if not tactic:
        flash('Brak dostępu do tej taktyki.', 'danger')
        return redirect(url_for('tactics.index'))

    map_id = tactic.map_id
    images = TacticImage.query.filter_by(tactic_id=tactic.id).all()
    for img in images:
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], img.filename)
        if os.path.exists(path):
            os.remove(path)
        db.session.delete(img)

    name = tactic.name
    db.session.delete(tactic)
    db.session.commit()
    flash(f'Usunięto taktykę „{name}”.', 'info')
    return redirect(url_for('tactics.map_tactics', map_id=map_id))


@tactics_bp.route('/tactic/<int:tactic_id>/save', methods=['POST'])
@login_required
def tactic_save(tactic_id):
    tactic = _owned_tactic_or_404(tactic_id)
    if not tactic:
        flash('Brak dostępu do tej taktyki.', 'danger')
        return redirect(url_for('tactics.index'))

    tactic.content = request.form.get('content', '')
    tactic.updated_by = current_user.id
    db.session.commit()
    flash('Zapisano opis taktyki.', 'success')
    return redirect(url_for('tactics.tactic_detail', tactic_id=tactic.id))


@tactics_bp.route('/tactic/<int:tactic_id>/board/save', methods=['POST'])
@login_required
def board_save(tactic_id):
    tactic = MapTactic.query.get_or_404(tactic_id)
    if not current_user.team or tactic.team_id != current_user.team.id:
        return jsonify(ok=False, error='forbidden'), 403

    payload = request.get_json(silent=True)
    cleaned = _clean_board_payload(payload)
    if cleaned is None:
        return jsonify(ok=False, error='invalid_payload'), 400

    tactic.board_data = json.dumps(cleaned)
    tactic.board_updated_by = current_user.id
    tactic.board_updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify(
        ok=True,
        updated_at=tactic.board_updated_at.strftime('%d.%m.%Y %H:%M'),
        updated_by=current_user.username,
    )


@tactics_bp.route('/tactic/<int:tactic_id>/board/reset', methods=['POST'])
@login_required
def board_reset(tactic_id):
    tactic = MapTactic.query.get_or_404(tactic_id)
    if not current_user.team or tactic.team_id != current_user.team.id:
        return jsonify(ok=False, error='forbidden'), 403

    tactic.board_data = json.dumps({'strokes': [], 'objects': []})
    tactic.board_updated_by = current_user.id
    tactic.board_updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify(ok=True)


@tactics_bp.route('/tactic/<int:tactic_id>/upload', methods=['POST'])
@login_required
def tactic_upload(tactic_id):
    tactic = _owned_tactic_or_404(tactic_id)
    if not tactic:
        flash('Brak dostępu do tej taktyki.', 'danger')
        return redirect(url_for('tactics.index'))

    file = request.files.get('image')
    if not file or file.filename == '':
        flash('Nie wybrano pliku.', 'danger')
        return redirect(url_for('tactics.tactic_detail', tactic_id=tactic.id))
    if not allowed_file(file.filename):
        flash('Niedozwolony format pliku (dozwolone: png, jpg, jpeg, gif, webp).', 'danger')
        return redirect(url_for('tactics.tactic_detail', tactic_id=tactic.id))

    ext = file.filename.rsplit('.', 1)[1].lower()
    fname = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))

    img = TacticImage(
        tactic_id=tactic.id, filename=fname,
        caption=request.form.get('caption', ''), uploaded_by=current_user.id
    )
    db.session.add(img)
    db.session.commit()
    flash('Dodano grafikę.', 'success')
    return redirect(url_for('tactics.tactic_detail', tactic_id=tactic.id))


@tactics_bp.route('/tactic/<int:tactic_id>/image/<int:image_id>/delete', methods=['POST'])
@login_required
def image_delete(tactic_id, image_id):
    tactic = _owned_tactic_or_404(tactic_id)
    if not tactic:
        flash('Brak dostępu do tej taktyki.', 'danger')
        return redirect(url_for('tactics.index'))

    img = TacticImage.query.filter_by(id=image_id, tactic_id=tactic.id).first_or_404()
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], img.filename)
    if os.path.exists(path):
        os.remove(path)
    db.session.delete(img)
    db.session.commit()
    flash('Usunięto grafikę.', 'info')
    return redirect(url_for('tactics.tactic_detail', tactic_id=tactic.id))
