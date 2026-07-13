import os
import uuid

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user

from extensions import db
from models import GameMap, MapPreference, MapTactic, TacticImage, Membership

tactics_bp = Blueprint('tactics', __name__, url_prefix='/tactics')

ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


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


@tactics_bp.route('/map/<int:map_id>')
@login_required
def map_detail(map_id):
    if not _require_team():
        return redirect(url_for('main.team_gate'))

    team = current_user.team
    game_map = GameMap.query.get_or_404(map_id)
    tactic = MapTactic.query.filter_by(team_id=team.id, map_id=map_id).first()
    images = (
        TacticImage.query.filter_by(tactic_id=tactic.id).order_by(TacticImage.uploaded_at.desc()).all()
        if tactic else []
    )
    return render_template('tactic_map.html', team=team, map=game_map, tactic=tactic, images=images)


@tactics_bp.route('/map/<int:map_id>/save', methods=['POST'])
@login_required
def map_save(map_id):
    if not _require_team():
        return redirect(url_for('main.team_gate'))

    team = current_user.team
    GameMap.query.get_or_404(map_id)
    content = request.form.get('content', '')

    tactic = MapTactic.query.filter_by(team_id=team.id, map_id=map_id).first()
    if not tactic:
        tactic = MapTactic(team_id=team.id, map_id=map_id, content=content, updated_by=current_user.id)
        db.session.add(tactic)
    else:
        tactic.content = content
        tactic.updated_by = current_user.id
    db.session.commit()
    flash('Zapisano taktykę.', 'success')
    return redirect(url_for('tactics.map_detail', map_id=map_id))


@tactics_bp.route('/map/<int:map_id>/upload', methods=['POST'])
@login_required
def map_upload(map_id):
    if not _require_team():
        return redirect(url_for('main.team_gate'))

    team = current_user.team
    GameMap.query.get_or_404(map_id)

    tactic = MapTactic.query.filter_by(team_id=team.id, map_id=map_id).first()
    if not tactic:
        tactic = MapTactic(team_id=team.id, map_id=map_id, content='', updated_by=current_user.id)
        db.session.add(tactic)
        db.session.flush()

    file = request.files.get('image')
    if not file or file.filename == '':
        flash('Nie wybrano pliku.', 'danger')
        return redirect(url_for('tactics.map_detail', map_id=map_id))
    if not allowed_file(file.filename):
        flash('Niedozwolony format pliku (dozwolone: png, jpg, jpeg, gif, webp).', 'danger')
        return redirect(url_for('tactics.map_detail', map_id=map_id))

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
    return redirect(url_for('tactics.map_detail', map_id=map_id))


@tactics_bp.route('/map/<int:map_id>/image/<int:image_id>/delete', methods=['POST'])
@login_required
def image_delete(map_id, image_id):
    img = TacticImage.query.get_or_404(image_id)
    tactic = MapTactic.query.get_or_404(img.tactic_id)
    if not current_user.team or tactic.team_id != current_user.team.id:
        flash('Brak dostępu.', 'danger')
        return redirect(url_for('main.dashboard'))

    path = os.path.join(current_app.config['UPLOAD_FOLDER'], img.filename)
    if os.path.exists(path):
        os.remove(path)
    db.session.delete(img)
    db.session.commit()
    flash('Usunięto grafikę.', 'info')
    return redirect(url_for('tactics.map_detail', map_id=map_id))
