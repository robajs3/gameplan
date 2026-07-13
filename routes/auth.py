from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db
from models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')

        if not username or not email or not password:
            flash('Wypełnij wszystkie pola.', 'danger')
        elif password != password2:
            flash('Hasła się nie zgadzają.', 'danger')
        elif len(password) < 6:
            flash('Hasło musi mieć co najmniej 6 znaków.', 'danger')
        elif User.query.filter_by(username=username).first():
            flash('Ta nazwa użytkownika jest zajęta.', 'danger')
        elif User.query.filter_by(email=email).first():
            flash('Ten adres e-mail jest już zarejestrowany.', 'danger')
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Konto utworzone! Dołącz do drużyny lub załóż nową.', 'success')
            return redirect(url_for('main.team_gate'))

    return render_template('register.html', pending_code=session.get('pending_join_code', ''))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier.lower())
        ).first()

        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))
        flash('Nieprawidłowa nazwa użytkownika/e-mail lub hasło.', 'danger')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Wylogowano.', 'info')
    return redirect(url_for('auth.login'))
