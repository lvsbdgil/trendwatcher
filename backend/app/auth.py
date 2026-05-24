"""Auth helpers: password hashing, JWT cookies, session management."""
from __future__ import annotations

import hashlib
import os
import secrets
import time
from pathlib import Path
from typing import Optional

import bcrypt
import jwt
from fastapi import Request, Response

from . import db
from .repositories import users as users_repo


COOKIE_NAME = "tw_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days
JWT_ALG = "HS256"

_cached_secret: Optional[str] = None


def _secret_file_path() -> Path:
    return Path(db.DB_PATH).parent / ".session_secret"


def _session_secret() -> str:
    global _cached_secret
    if _cached_secret:
        return _cached_secret

    env_secret = os.environ.get("SESSION_SECRET") or os.environ.get("JWT_SECRET")
    if env_secret:
        _cached_secret = env_secret
        return _cached_secret

    path = _secret_file_path()
    try:
        if path.exists():
            value = path.read_text(encoding="utf-8").strip()
            if value:
                _cached_secret = value
                return _cached_secret
    except OSError:
        pass

    new_secret = secrets.token_hex(32)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_secret, encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except OSError:
        pass

    _cached_secret = new_secret
    return _cached_secret


def prehash(plain: str) -> str:
    """SHA-256 pre-hash — mirrors frontend hashPassword(). Apply before hash_password()."""
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def hash_password(prehashed: str) -> str:
    """bcrypt-wrap an already-prehashed (SHA-256) password."""
    return bcrypt.hashpw(prehashed.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def make_token(user_id: int, username: str, role: str) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + COOKIE_MAX_AGE,
    }
    return jwt.encode(payload, _session_secret(), algorithm=JWT_ALG)


def decode_token(token: str) -> Optional[dict]:
    if not token:
        return None
    try:
        return jwt.decode(token, _session_secret(), algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        return None


def set_session_cookie(response: Response, token: str) -> None:
    secure = os.environ.get("SESSION_COOKIE_SECURE", "").lower() in {"1", "true", "yes"}
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/")


def get_current_user(request: Request) -> Optional[dict]:
    token = request.cookies.get(COOKIE_NAME)
    payload = decode_token(token) if token else None
    if not payload:
        return None
    try:
        user_id = int(payload.get("sub", "0"))
    except (TypeError, ValueError):
        return None

    user = users_repo.find_by_id(user_id)
    if not user:
        return None
    users_repo.touch_seen(user_id)
    return user


def find_user(username: str) -> Optional[dict]:
    if not username:
        return None
    return users_repo.find_by_username(username)


def create_user(username: str, password: str, role: str = "user") -> Optional[dict]:
    return users_repo.create(username, hash_password(password), role)


def touch_login(user_id: int) -> None:
    users_repo.touch_login(user_id)


def ensure_admin_from_env() -> None:
    login = os.environ.get("ADMIN_LOGIN", "").strip().lower()
    password_hash = os.environ.get("ADMIN_PASSWORD_HASH", "").strip()
    plain_password = os.environ.get("ADMIN_PASSWORD", "").strip()

    if not login:
        return
    if not password_hash and plain_password:
        password_hash = hash_password(prehash(plain_password))
    if not password_hash:
        return

    users_repo.ensure_admin(login, password_hash)
