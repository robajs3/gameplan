from datetime import date, timedelta, datetime
from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_required, current_user

from extensions import db
from models import Team, Membership, User, Availability, DaySession, generate_code

main_bp = Blueprint('main', __name__)

DAY_NAMES_PL = ['Pon', 'Wt', 'Śr', 'Czw', 'Pt', 'Sob', 'Niedz']
MONTH_NAMES_PL = ['', 'sty', 'lut', 'mar', 'kwi', 'maj', 'cze', 'lip', 'sie', 'wrz', 'paź', 'lis', 'gru']


def team_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.membership:
            flash('Najpierw dołącz do drużyny lub ją utwórz.', 'warning')
            return redirect(url_for('main.team_gate'))
        return f(*args, **kwargs)
    return wrapper


@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main_bp.route('/team', methods=['GET'])
@login_required
def team_gate():
    if current_user.membership:
        return redirect(url_for('main.dashboard'))
    return render_template('team_gate.html', pending_code=session.get('pending_join_code', ''))


@main_bp.route('/team/create', methods=['POST'])
@login_required
def team_create():
    if current_user.membership:
        flash('Jesteś już w drużynie.', 'warning')
        return redirect(url_for('main.dashboard'))

    name = request.form.get('name', '').strip()
    if not name:
        flash('Podaj nazwę drużyny.', 'danger')
        return redirect(url_for('main.team_gate'))

    code = generate_code()
    while Team.query.filter_by(join_code=code).first():
        code = generate_code()

    team = Team(name=name, join_code=code, owner_id=current_user.id)
    db.session.add(team)
    db.session.flush()

    db.session.add(Membership(user_id=current_user.id, team_id=team.id, role='player'))
    db.session.commit()

    session.pop('pending_join_code', None)
    flash(f'Drużyna „{name}” utworzona! Kod dołączenia: {code}', 'success')
    return redirect(url_for('main.dashboard'))


@main_bp.route('/team/join', methods=['POST'])
@login_required
def team_join():
    if current_user.membership:
        flash('Jesteś już w drużynie.', 'warning')
        return redirect(url_for('main.dashboard'))

    code = request.form.get('code', '').strip().upper()
    role = request.form.get('role', 'reserve')
    if role not in ('player', 'reserve'):
        role = 'reserve'

    team = Team.query.filter_by(join_code=code).first()
    if not team:
        flash('Nieprawidłowy kod drużyny.', 'danger')
        return redirect(url_for('main.team_gate'))

    db.session.add(Membership(user_id=current_user.id, team_id=team.id, role=role))
    db.session.commit()

    session.pop('pending_join_code', None)
    flash(f'Dołączono do drużyny „{team.name}”!', 'success')
    return redirect(url_for('main.dashboard'))


@main_bp.route('/team/info')
@login_required
@team_required
def team_info():
    team = current_user.team
    members = (
        Membership.query.filter_by(team_id=team.id)
        .join(User)
        .order_by(Membership.role.desc(), User.username)
        .all()
    )
    invite_link = url_for('main.team_join_link', code=team.join_code, _external=True)
    return render_template('team_info.html', team=team, members=members, invite_link=invite_link)


@main_bp.route('/team/leave', methods=['POST'])
@login_required
@team_required
def team_leave():
    db.session.delete(current_user.membership)
    db.session.commit()
    flash('Opuściłeś drużynę.', 'info')
    return redirect(url_for('main.team_gate'))


@main_bp.route('/j/<code>')
def team_join_link(code):
    session['pending_join_code'] = code.upper()
    if current_user.is_authenticated:
        return redirect(url_for('main.team_gate'))
    return redirect(url_for('auth.register'))


@main_bp.route('/dashboard')
@login_required
@team_required
def dashboard():
    team = current_user.team
    start = date.today()
    days = [start + timedelta(days=i) for i in range(14)]

    members = Membership.query.filter_by(team_id=team.id).join(User).order_by(User.username).all()

    avail_rows = Availability.query.filter(
        Availability.team_id == team.id,
        Availability.date >= days[0],
        Availability.date <= days[-1],
    ).all()
    avail_map = {}
    for row in avail_rows:
        avail_map.setdefault(row.date.isoformat(), {})[row.user_id] = row

    session_rows = DaySession.query.filter(
        DaySession.team_id == team.id,
        DaySession.date >= days[0],
        DaySession.date <= days[-1],
    ).order_by(DaySession.time_from).all()
    sessions_map = {}
    for s in session_rows:
        sessions_map.setdefault(s.date.isoformat(), []).append(s)

    my_avail = {row.date.isoformat(): row for row in avail_rows if row.user_id == current_user.id}

    calendar_data = []
    for d in days:
        iso = d.isoformat()
        day_members = []
        for m in members:
            row = avail_map.get(iso, {}).get(m.user_id)
            if row:
                day_members.append({
                    'username': m.user.username,
                    'role': m.role,
                    'status': row.status,
                    'time_from': row.time_from,
                    'time_to': row.time_to,
                })
            else:
                day_members.append({
                    'username': m.user.username,
                    'role': m.role,
                    'status': 'unknown',
                    'time_from': None,
                    'time_to': None,
                })

        my_row = my_avail.get(iso)
        calendar_data.append({
            'date': iso,
            'day_name': DAY_NAMES_PL[d.weekday()],
            'day_num': d.day,
            'month_name': MONTH_NAMES_PL[d.month],
            'is_today': d == start,
            'is_weekend': d.weekday() >= 5,
            'members': day_members,
            'sessions': sessions_map.get(iso, []),
            'my_status': my_row.status if my_row else '',
            'my_time_from': my_row.time_from if my_row else '',
            'my_time_to': my_row.time_to if my_row else '',
            'my_note': my_row.note if my_row else '',
        })

    return render_template('dashboard.html', team=team, calendar_data=calendar_data)


@main_bp.route('/dashboard/availability', methods=['POST'])
@login_required
@team_required
def set_availability():
    d = request.form.get('date')
    status = request.form.get('status')
    time_from = request.form.get('time_from') or None
    time_to = request.form.get('time_to') or None
    note = request.form.get('note') or None

    try:
        day = datetime.strptime(d, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        flash('Nieprawidłowa data.', 'danger')
        return redirect(url_for('main.dashboard'))

    if status not in ('available', 'unavailable'):
        flash('Nieprawidłowy status.', 'danger')
        return redirect(url_for('main.dashboard'))

    row = Availability.query.filter_by(user_id=current_user.id, date=day).first()
    if not row:
        row = Availability(user_id=current_user.id, team_id=current_user.team.id, date=day)
        db.session.add(row)

    row.status = status
    row.time_from = time_from if status == 'available' else None
    row.time_to = time_to if status == 'available' else None
    row.note = note
    db.session.commit()
    flash('Zapisano Twoją dostępność.', 'success')
    return redirect(url_for('main.dashboard') + f'#day-{d}')


@main_bp.route('/dashboard/availability/copy', methods=['POST'])
@login_required
@team_required
def copy_availability():
    """Kopiuje dostępność (status + godziny) bieżącego użytkownika z dnia
    źródłowego na dzień docelowy (drag & drop w kalendarzu).

    Warunek: jeśli w dniu docelowym użytkownik ma już zapisaną dostępność
    z innymi godzinami niż w dniu źródłowym, kopiowanie jest odrzucane —
    żeby przypadkowe przeciągnięcie nie nadpisało innych, celowo ustawionych
    godzin. Jeśli dzień docelowy jest pusty albo ma już te same godziny,
    kopiowanie jest wykonywane.
    """
    data = request.get_json(silent=True) or {}
    source_str = data.get('source_date')
    target_str = data.get('target_date')

    try:
        source_day = datetime.strptime(source_str, '%Y-%m-%d').date()
        target_day = datetime.strptime(target_str, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return jsonify(ok=False, message='Nieprawidłowa data.'), 400

    if source_day == target_day:
        return jsonify(ok=False, message='Dzień źródłowy i docelowy są takie same.'), 400

    source_row = Availability.query.filter_by(user_id=current_user.id, date=source_day).first()
    if not source_row:
        return jsonify(ok=False, message='Brak ustawionej dostępności w dniu źródłowym.'), 400

    target_row = Availability.query.filter_by(user_id=current_user.id, date=target_day).first()

    if target_row and (
        target_row.time_from != source_row.time_from or target_row.time_to != source_row.time_to
    ):
        return jsonify(
            ok=False,
            message='W dniu docelowym masz już ustawione inne godziny dostępności.',
        ), 409

    if not target_row:
        target_row = Availability(user_id=current_user.id, team_id=current_user.team.id, date=target_day)
        db.session.add(target_row)

    target_row.status = source_row.status
    target_row.time_from = source_row.time_from
    target_row.time_to = source_row.time_to
    target_row.note = source_row.note
    db.session.commit()

    return jsonify(ok=True, message='Skopiowano dostępność.', date=target_str)


@main_bp.route('/dashboard/session', methods=['POST'])
@login_required
@team_required
def add_session():
    d = request.form.get('date')
    type_ = request.form.get('type')
    time_from = request.form.get('time_from') or None
    time_to = request.form.get('time_to') or None
    note = request.form.get('note') or None

    try:
        day = datetime.strptime(d, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        flash('Nieprawidłowa data.', 'danger')
        return redirect(url_for('main.dashboard'))

    if type_ not in ('training', 'casual', 'match'):
        flash('Nieprawidłowy typ wydarzenia.', 'danger')
        return redirect(url_for('main.dashboard'))

    s = DaySession(
        team_id=current_user.team.id, date=day, type=type_,
        time_from=time_from, time_to=time_to, note=note, created_by=current_user.id
    )
    db.session.add(s)
    db.session.commit()
    flash('Dodano wydarzenie do kalendarza.', 'success')
    return redirect(url_for('main.dashboard') + f'#day-{d}')


@main_bp.route('/dashboard/session/<int:session_id>/delete', methods=['POST'])
@login_required
@team_required
def delete_session(session_id):
    s = DaySession.query.get_or_404(session_id)
    if s.team_id != current_user.team.id:
        flash('Brak dostępu.', 'danger')
        return redirect(url_for('main.dashboard'))
    if s.created_by != current_user.id and current_user.team.owner_id != current_user.id:
        flash('Możesz usuwać tylko własne wpisy.', 'danger')
        return redirect(url_for('main.dashboard'))

    d_iso = s.date.isoformat()
    db.session.delete(s)
    db.session.commit()
    flash('Usunięto wpis.', 'info')
    return redirect(url_for('main.dashboard') + f'#day-{d_iso}')
