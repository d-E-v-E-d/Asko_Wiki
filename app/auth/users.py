from __future__ import annotations
from typing import Dict, Optional
from pathlib import Path
import json
from passlib.hash import bcrypt
from app.config import config

# Pfad robust auf Projektwurzel beziehen
_rel = config.get('auth', 'users_file') or 'app/auth/users.json'
USERS_FILE = (config.project_root() / _rel).resolve()

# In-Memory Cache
USERS: Dict[str, dict] = {}

DEFAULT_USERS = {
    'admin':  {'password_hash': bcrypt.hash('admin123'),  'role': 'admin'},
    'editor': {'password_hash': bcrypt.hash('editor123'), 'role': 'editor'},
}

def _read_json(path: Path) -> Dict[str, dict]:
    try:
        return json.loads(path.read_text(encoding='utf-8') or '{}')
    except Exception:
        return {}

def _write_json(path: Path, data: Dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def _ensure_defaults(d: Dict[str, dict]) -> Dict[str, dict]:
    # Admin/Editor anlegen, wenn fehlen
    if 'admin' not in d:
        d['admin'] = DEFAULT_USERS['admin']
    if 'editor' not in d:
        d['editor'] = DEFAULT_USERS['editor']
    return d

def load_users() -> Dict[str, dict]:
    global USERS
    print("USERS_FILE ->", USERS_FILE)
    data = _read_json(USERS_FILE) if USERS_FILE.exists() else {}
    # Sicherheits-Filter + Defaults
    cleaned: Dict[str, dict] = {}
    for u, v in data.items():
        if isinstance(v, dict) and 'password_hash' in v and 'role' in v:
            cleaned[u] = {'password_hash': v['password_hash'], 'role': v['role']}
    USERS = _ensure_defaults(cleaned)
    _write_json(USERS_FILE, USERS)  # zurückschreiben, falls Defaults ergänzt
    return USERS

def save_users() -> None:
    _write_json(USERS_FILE, USERS)

def get_user(username: str) -> Optional[dict]:
    if not USERS:
        load_users()
    return USERS.get(username)

def add_user(username: str, password: str, role: str = 'editor') -> None:
    if not USERS:
        load_users()
    if username in USERS:
        raise ValueError('User exists')
    USERS[username] = {'password_hash': bcrypt.hash(password[:72]), 'role': role}
    save_users()

def update_password(username: str, new_password: str) -> None:
    if not USERS:
        load_users()
    if username not in USERS:
        raise ValueError('User not found')
    USERS[username]['password_hash'] = bcrypt.hash(new_password[:72])
    save_users()

def delete_user(username: str) -> None:
    if not USERS:
        load_users()
    USERS.pop(username, None)
    save_users()
