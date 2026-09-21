"""Integracja GamePlan z LoginHub (SSO): auto-logowanie i auto-zakładanie kont."""
import logging
import os
import secrets

from flask import redirect, request
from flask_login import current_user, login_user

import sso_client
from extensions import db
from models import User

log = logging.getLogger(__name__)

APP_SLUG = "gameplan"
EMAIL_DOMAIN = "sso.local"
HUB_LOGIN = os.environ.get("HUB_LOGIN_URL", "/auth/login")
NEXT_PATH = os.environ.get("SSO_NEXT_PATH", "/gameplan/")


def _create_user(hub_username):
    # get-or-create po e-mailu wyprowadzonym z loginu huba (idempotentne);
    # NIE po username, żeby nie przejąć istniejącego, ręcznie założonego konta
    email = f"{hub_username}@{EMAIL_DOMAIN}"
    existing = User.query.filter_by(email=email).first()
    if existing:
        return existing.id, existing.username

    username, n = hub_username, 1
    while User.query.filter_by(username=username).first():
        n += 1
        username = f"{hub_username}{n}"

    user = User(username=username, email=email)
    user.set_password(secrets.token_urlsafe(24))  # nieużywane, logowanie idzie przez SSO
    db.session.add(user)
    db.session.commit()
    return user.id, user.username


def init_sso(app):
    @app.before_request
    def _sso_autologin():
        if request.endpoint in (None, "static") or current_user.is_authenticated:
            return

        local_id = sso_client.resolve_or_create_local_user(
            app_slug=APP_SLUG, create_user=_create_user)
        if local_id:
            user = db.session.get(User, local_id)
            if user:
                login_user(user)
                return

        has_cookie = bool(request.cookies.get("sso_session"))
        if has_cookie:
            log.warning("SSO: jest ciasteczko huba, ale nie udało się zalogować "
                        "(sprawdź HUB_INTERNAL_URL / SSO_SECRET / sieć sso_net)")

        # brak ciasteczka -> logowanie w hubie zamiast lokalnego formularza
        # (z ciasteczkiem, ale bez działającego SSO, zostaje lokalny /login — bez pętli;
        # awaryjnie zawsze działa /login?local=1)
        if (request.endpoint in ("auth.login", "auth.register")
                and not has_cookie and not request.args.get("local")):
            return redirect(sso_client.login_url(NEXT_PATH, HUB_LOGIN.rsplit("/login", 1)[0]))

    @app.after_request
    def _sso_global_logout(response):
        if request.endpoint == "auth.logout":
            sso_client.clear_sso_cookie(response)  # inaczej autologin zaloguje z powrotem
        return response
