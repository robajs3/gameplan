import os
import uuid
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user

from extensions import db
from models import Match, MatchImage, GameMap

matches_bp = Blueprint('matches', __name__, url_prefix='/matches')

ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def _require_team():
    if not current_user.membership:
        flash('Najpierw dołącz do drużyny.', 'warning')
        return False
    return True


@matches_bp.route('/')
@login_required
def index():
    if not _require_team():
        return redirect(url_for('main.team_gate'))

    team = current_user.team
    today = datetime.utcnow().date()
    upcoming = Match.query.filter(Match.team_id == team.id, Match.match_date >= today).order_by(Match.match_date).all()
    past = Match.query.filter(Match.team_id == team.id, Match.match_date < today).order_by(Match.match_date.desc()).all()
    return render_template('matches.html', team=team, upcoming=upcoming, past=past)


@matches_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_match():
    if not _require_team():
        return redirect(url_for('main.team_gate'))

    maps = GameMap.query.order_by(GameMap.id).all()

    if request.method == 'POST':
        opponent = request.form.get('opponent', '').strip()
        match_date = request.form.get('match_date')
        match_time = request.form.get('match_time') or None
        match_room = request.form.get('match_room', '')
        maps_plan = ','.join(request.form.getlist('maps_plan'))
        analysis = request.form.get('analysis', '')

        if not opponent or not match_date:
            flash('Podaj przeciwnika i datę meczu.', 'danger')
            return render_template('match_new.html', maps=maps)

        try:
            d = datetime.strptime(match_date, '%Y-%m-%d').date()
        except ValueError:
            flash('Nieprawidłowa data.', 'danger')
            return render_template('match_new.html', maps=maps)

        m = Match(
            team_id=current_user.team.id, opponent=opponent, match_date=d, match_time=match_time,
            match_room=match_room, maps_plan=maps_plan, analysis=analysis, created_by=current_user.id
        )
        db.session.add(m)
        db.session.commit()
        flash('Mecz dodany!', 'success')
        return redirect(url_for('matches.detail', match_id=m.id))

    return render_template('match_new.html', maps=maps)


@matches_bp.route('/<int:match_id>')
@login_required
def detail(match_id):
    m = Match.query.get_or_404(match_id)
    if not current_user.team or m.team_id != current_user.team.id:
        flash('Brak dostępu.', 'danger')
        return redirect(url_for('matches.index'))

    maps = {gm.key: gm.display_name for gm in GameMap.query.all()}
    maps_plan_list = [maps.get(k, k) for k in (m.maps_plan.split(',') if m.maps_plan else []) if k]
    images = MatchImage.query.filter_by(match_id=m.id).order_by(MatchImage.uploaded_at.desc()).all()
    all_maps = GameMap.query.order_by(GameMap.id).all()
    current_plan_keys = set((m.maps_plan or '').split(',')) if m.maps_plan else set()

    return render_template(
        'match_detail.html', m=m, maps_plan_list=maps_plan_list,
        images=images, all_maps=all_maps, current_plan_keys=current_plan_keys
    )


@matches_bp.route('/<int:match_id>/edit', methods=['POST'])
@login_required
def edit(match_id):
    m = Match.query.get_or_404(match_id)
    if not current_user.team or m.team_id != current_user.team.id:
        flash('Brak dostępu.', 'danger')
        return redirect(url_for('matches.index'))

    m.match_room = request.form.get('match_room', m.match_room)
    m.analysis = request.form.get('analysis', m.analysis)
    m.maps_plan = ','.join(request.form.getlist('maps_plan'))
    db.session.commit()
    flash('Zaktualizowano mecz.', 'success')
    return redirect(url_for('matches.detail', match_id=match_id))


@matches_bp.route('/<int:match_id>/upload', methods=['POST'])
@login_required
def upload_image(match_id):
    m = Match.query.get_or_404(match_id)
    if not current_user.team or m.team_id != current_user.team.id:
        flash('Brak dostępu.', 'danger')
        return redirect(url_for('matches.index'))

    file = request.files.get('image')
    if not file or file.filename == '' or not allowed_file(file.filename):
        flash('Nieprawidłowy plik (dozwolone: png, jpg, jpeg, gif, webp).', 'danger')
        return redirect(url_for('matches.detail', match_id=match_id))

    ext = file.filename.rsplit('.', 1)[1].lower()
    fname = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))

    img = MatchImage(match_id=m.id, filename=fname, caption=request.form.get('caption', ''), uploaded_by=current_user.id)
    db.session.add(img)
    db.session.commit()
    flash('Dodano grafikę.', 'success')
    return redirect(url_for('matches.detail', match_id=match_id))


@matches_bp.route('/<int:match_id>/delete', methods=['POST'])
@login_required
def delete_match(match_id):
    m = Match.query.get_or_404(match_id)
    if not current_user.team or m.team_id != current_user.team.id:
        flash('Brak dostępu.', 'danger')
        return redirect(url_for('matches.index'))

    db.session.delete(m)
    db.session.commit()
    flash('Usunięto mecz.', 'info')
    return redirect(url_for('matches.index'))
