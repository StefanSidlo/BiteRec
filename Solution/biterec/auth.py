"""
auth.py  --  BiteRec file-based accounts
==========================================

A tiny, dependency-light user store backed by a single JSON file
(data/users.json). No database required, as requested.

Each user record holds:
  * a salted password hash (werkzeug)
  * allergen hard-constraints
  * the health/eco priority weight
  * a list of favourite product ids

Passwords are never stored in clear text. The store is process-safe enough
for a single-process local demo (load -> mutate -> save).
"""

import os
import json
import threading
from werkzeug.security import generate_password_hash, check_password_hash

HERE = os.path.dirname(os.path.abspath(__file__))
USERS_JSON = os.path.join(HERE, "data", "users.json")

_lock = threading.Lock()


def _load():
    if not os.path.exists(USERS_JSON):
        return {}
    try:
        with open(USERS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(users):
    os.makedirs(os.path.dirname(USERS_JSON), exist_ok=True)
    tmp = USERS_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=1)
    os.replace(tmp, USERS_JSON)


def _default_record(password):
    return {
        "password_hash": generate_password_hash(password),
        "allergens": [],
        "health_weight": 0.7,      # default 70% health / 30% eco (FR-03)
        "show_health": True,       # show the "Better for You" alternative
        "show_eco": True,          # show the "Better for Earth" alternative
        "onboarded": False,        # set True once the user saves preferences
        "favorites": [],
    }


def register(username, password):
    username = (username or "").strip().lower()
    if not username or not password:
        return False, "Username and password are required."
    if len(password) < 4:
        return False, "Password must be at least 4 characters."
    with _lock:
        users = _load()
        if username in users:
            return False, "That username is already taken."
        users[username] = _default_record(password)
        _save(users)
    return True, "Account created."


def authenticate(username, password):
    username = (username or "").strip().lower()
    with _lock:
        users = _load()
        rec = users.get(username)
    if not rec or not check_password_hash(rec["password_hash"], password):
        return False, "Invalid username or password."
    return True, "Signed in."


def get_profile(username):
    username = (username or "").strip().lower()
    with _lock:
        users = _load()
        rec = users.get(username)
    if not rec:
        return None
    return {
        "username": username,
        "allergens": rec.get("allergens", []),
        "health_weight": rec.get("health_weight", 0.7),
        "show_health": rec.get("show_health", True),
        "show_eco": rec.get("show_eco", True),
        "onboarded": rec.get("onboarded", False),
        "favorites": rec.get("favorites", []),
    }


def update_preferences(username, allergens=None, health_weight=None,
                       show_health=None, show_eco=None):
    username = (username or "").strip().lower()
    with _lock:
        users = _load()
        rec = users.get(username)
        if not rec:
            return None
        if allergens is not None:
            rec["allergens"] = list(allergens)
        if health_weight is not None:
            rec["health_weight"] = max(0.0, min(1.0, float(health_weight)))
        if show_health is not None:
            rec["show_health"] = bool(show_health)
        if show_eco is not None:
            rec["show_eco"] = bool(show_eco)
        rec["onboarded"] = True
        users[username] = rec
        _save(users)
    return get_profile(username)


def toggle_favorite(username, product_id):
    username = (username or "").strip().lower()
    with _lock:
        users = _load()
        rec = users.get(username)
        if not rec:
            return None
        favs = rec.get("favorites", [])
        if product_id in favs:
            favs.remove(product_id)
        else:
            favs.append(product_id)
        rec["favorites"] = favs
        users[username] = rec
        _save(users)
    return rec["favorites"]
