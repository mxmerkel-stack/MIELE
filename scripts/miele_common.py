"""Gemeinsame Helfer für die Miele-Third-Party-API (developer.miele.com)."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

AUTH_URL = "https://auth.domestic.miele-iot.com/partner/realms/mcs/protocol/openid-connect/auth"
TOKEN_URL ="https://auth.domestic.miele-iot.com/partner/realms/mcs/protocol/openid-connect/token"
API_BASE = "https://api.mcs3.miele.com/v1"
REDIRECT_URI = "http://localhost"


def _die(msg):
    if os.environ.get("GITHUB_ACTIONS"):
        print("::error::" + msg.replace("\n", " "))
    raise SystemExit(msg)


def _post_form(url, data):
    req = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(data).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        _die(f"Token-Anfrage fehlgeschlagen: HTTP {e.code} {e.read().decode()[:300]}")


def exchange_code(client_id, client_secret, code):
    return _post_form(TOKEN_URL, {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "client_secret": client_secret,
    })


def refresh(client_id, client_secret, refresh_token):
    return _post_form(TOKEN_URL, {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    })


def api_get(path, access_token):
    req = urllib.request.Request(
        API_BASE + path,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        _die(f"API-Anfrage {path} fehlgeschlagen: HTTP {e.code} {e.read().decode()[:300]}")
