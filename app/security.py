# app/security.py
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
import os

import jwt  # PyJWT
from passlib.hash import bcrypt

from app.config import config

# ---- Konfiguration: Secret & Ablaufzeit bestimmen (Priorität: config -> ENV -> Default) ----
CFG_SECRET = None
try:
    # falls vorhanden: aus config.ini / config.json
    CFG_SECRET = config.get('security', 'jwt_secret')
except Exception:
    pass

JWT_SECRET: str = (CFG_SECRET or os.environ.get("JWT_SECRET") or "dev-secret-change-me")
JWT_ALG: str = "HS256"
JWT_EXP_MIN = int(config.get('security', 'jwt_exp_minutes', 480))

# Ablauf in Minuten: config.security.jwt_exp_minutes -> ENV JWT_EXP_MIN -> Default 480 (8h)
def _int_or(default: int, *vals: Optional[str]) -> int:
    for v in vals:
        if v is None:
            continue
        try:
            return int(v)
        except Exception:
            continue
    return default

CFG_EXP = None
try:
    CFG_EXP = config.get('security', 'jwt_exp_minutes', default=None)
except Exception:
    pass

# ---- Rollenrechte (wird von deps.py meist genutzt) ----
ROLE_PERMS: Dict[str, list[str]] = {
    'reader': ['read'],
    'editor': ['read', 'draft'],
    'admin':  ['read', 'draft', 'approve', 'publish'],
}

# ---- Passwort-Utilities ----
def verify_password(plain: str, hashed: str) -> bool:
    # bcrypt akzeptiert maximal 72 Bytes im Klartext
    return bcrypt.verify((plain or "")[:72], hashed)

# ---- JWT-Utilities ----
# app/security.py – create_token(...):
def create_token(sub: str, role: str, name: str | None = None, exp_min: Optional[int] = None) -> str:
    if exp_min is None:
        exp_min = JWT_EXP_MIN
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=exp_min)).timestamp()),
    }
    if name:
        payload["name"] = name
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_token(token: str) -> dict:
    """Validiert & decodiert das JWT; wirft jwt.ExpiredSignatureError / jwt.InvalidTokenError bei Fehlern."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
