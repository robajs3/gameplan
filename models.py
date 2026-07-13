import secrets
import string
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


def generate_code(length=8):
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


MAP_POOL = ['anubis', 'ancient', 'cache', 'mirage', 'dust2', 'inferno', 'nuke']


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    membership = db.relationship(
        'Membership', backref='user', uselist=False, cascade='all, delete-orphan'
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def team(self):
        return self.membership.team if self.membership else None

    @property
    def role(self):
        return self.membership.role if self.membership else None


class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    join_code = db.Column(db.String(16), unique=True, nullable=False, default=generate_code)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    members = db.relationship('Membership', backref='team', cascade='all, delete-orphan')


class Membership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='reserve')  # 'player' / 'reserve'
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)


class Availability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # 'available' / 'unavailable'
    time_from = db.Column(db.String(5))
    time_to = db.Column(db.String(5))
    note = db.Column(db.String(200))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'date', name='uq_availability_user_date'),)


class DaySession(db.Model):
    """Aktywność drużyny w danym dniu: trening / luźne granie / mecz."""
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'training' / 'casual' / 'match'
    time_from = db.Column(db.String(5))
    time_to = db.Column(db.String(5))
    note = db.Column(db.String(200))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship('User')


class GameMap(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(40), unique=True, nullable=False)
    display_name = db.Column(db.String(60), nullable=False)


class MapPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    map_id = db.Column(db.Integer, db.ForeignKey('game_map.id'), nullable=False)
    points = db.Column(db.Integer, nullable=False)  # 0-6

    __table_args__ = (db.UniqueConstraint('user_id', 'map_id', name='uq_pref_user_map'),)


class MapTactic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    map_id = db.Column(db.Integer, db.ForeignKey('game_map.id'), nullable=False)
    content = db.Column(db.Text, default='')
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('team_id', 'map_id', name='uq_tactic_team_map'),)


class TacticImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tactic_id = db.Column(db.Integer, db.ForeignKey('map_tactic.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    caption = db.Column(db.String(200))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    opponent = db.Column(db.String(120), nullable=False)
    match_date = db.Column(db.Date, nullable=False)
    match_time = db.Column(db.String(5))
    match_room = db.Column(db.Text)
    maps_plan = db.Column(db.Text)  # klucze map po przecinku
    analysis = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MatchImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    caption = db.Column(db.String(200))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
