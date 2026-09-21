"""sso_client.py — wspólny moduł SSO dla appek podpiętych pod LoginHub
(kopia z loginhub/sso_client.py; SALT musi być identyczny jak w LoginHub)."""

import os
from urllib.parse import quote

import requests
from flask import request
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

_SALT = "sso-hub-v1"


def _verify_cookie(sso_secret, token, max_age_seconds):
    s = URLSafeTimedSerializer(sso_secret, salt=_SALT)
    try:
        return s.loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None


def _cfg(cookie_name, sso_secret, hub_internal_url, max_age_days):
    return (
        cookie_name or os.environ.get("SSO_COOKIE_NAME", "sso_session"),
        sso_secret or os.environ.get("SSO_SECRET"),
        (hub_internal_url or os.environ.get("HUB_INTERNAL_URL", "http://127.0.0.1:8011")).rstrip("/"),
        max_age_days or int(os.environ.get("SSO_SESSION_DAYS", "30")),
    )


def resolve_local_user_id(app_slug, cookie_name=None, sso_secret=None,
                          hub_internal_url=None, max_age_days=None):
    """Lokalny user_id, jeśli ciasteczko LoginHub jest ważne i konto jest połączone; inaczej None."""
    cookie_name, sso_secret, hub_internal_url, max_age_days = _cfg(
        cookie_name, sso_secret, hub_internal_url, max_age_days)
    if not sso_secret:
        return None
    token = request.cookies.get(cookie_name)
    if not token:
        return None
    data = _verify_cookie(sso_secret, token, max_age_days * 86400)
    if not data:
        return None
    try:
        resp = requests.get(
            f"{hub_internal_url}/api/resolve",
            params={"app_slug": app_slug, "hub_user_id": data["hub_user_id"]},
            headers={"X-SSO-Api-Key": sso_secret},
            timeout=3,
        )
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    payload = resp.json()
    if not payload.get("linked"):
        return None
    return payload["local_user_id"]


def resolve_or_create_local_user(app_slug, create_user, cookie_name=None, sso_secret=None,
                                 hub_internal_url=None, max_age_days=None):
    """Jak resolve_local_user_id, ale przy braku połączenia zakłada konto przez
    create_user(hub_username) -> (local_user_id, local_username) i zgłasza je do Huba."""
    cookie_name, sso_secret, hub_internal_url, max_age_days = _cfg(
        cookie_name, sso_secret, hub_internal_url, max_age_days)
    if not sso_secret:
        return None
    token = request.cookies.get(cookie_name)
    if not token:
        return None
    data = _verify_cookie(sso_secret, token, max_age_days * 86400)
    if not data:
        return None
    hub_user_id = data["hub_user_id"]
    try:
        resp = requests.get(
            f"{hub_internal_url}/api/resolve",
            params={"app_slug": app_slug, "hub_user_id": hub_user_id},
            headers={"X-SSO-Api-Key": sso_secret},
            timeout=3,
        )
    except requests.RequestException:
        return None
    if resp.status_code == 200:
        payload = resp.json()
        if payload.get("linked"):
            return payload["local_user_id"]
    elif resp.status_code != 404:
        return None
    try:
        local_user_id, local_username = create_user(data["username"])
    except Exception:
        return None
    try:
        requests.post(
            f"{hub_internal_url}/api/link",
            json={
                "app_slug": app_slug,
                "hub_user_id": hub_user_id,
                "local_user_id": local_user_id,
                "local_username": local_username,
            },
            headers={"X-SSO-Api-Key": sso_secret},
            timeout=3,
        )
    except requests.RequestException:
        pass
    return local_user_id


def login_url(next_path, hub_public_prefix="/auth"):
    return f"{hub_public_prefix}/login?next={quote(next_path)}"


def clear_sso_cookie(response, cookie_name=None):
    cookie_name = cookie_name or os.environ.get("SSO_COOKIE_NAME", "sso_session")
    response.delete_cookie(cookie_name, path="/")
    return response
