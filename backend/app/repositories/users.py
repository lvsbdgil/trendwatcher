from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .. import db


def find_by_username(username: str) -> Optional[dict]:
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username = ?",
            (username.strip().lower(),),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def find_by_id(user_id: int) -> Optional[dict]:
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, username, role, created_at, last_login_at, last_seen_at "
            "FROM users WHERE id = ?",
            (user_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def create(username: str, password_hash: str, role: str = "user") -> Optional[dict]:
    login = username.strip().lower()
    if not login:
        return None
    now = _now()
    try:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, role, last_login_at, last_seen_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (login, password_hash, role, now, now),
            )
            return {"id": cur.lastrowid, "username": login, "role": role}
    except Exception:
        return None


def touch_login(user_id: int) -> None:
    now = _now()
    with db.cursor() as cur:
        cur.execute(
            "UPDATE users SET last_login_at = ?, last_seen_at = ? WHERE id = ?",
            (now, now, user_id),
        )


def touch_seen(user_id: int) -> None:
    with db.cursor() as cur:
        cur.execute(
            "UPDATE users SET last_seen_at = ? WHERE id = ?",
            (_now(), user_id),
        )


def get_password_hash(user_id: int) -> Optional[str]:
    with db.cursor() as cur:
        cur.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
    return row["password_hash"] if row else None


def update_password(user_id: int, password_hash: str) -> None:
    with db.cursor() as cur:
        cur.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id),
        )


def count() -> int:
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM users")
        return cur.fetchone()["c"]


def list_with_action_count() -> list[dict]:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT u.id, u.username, u.role, u.created_at, u.last_login_at, u.last_seen_at,
                   (SELECT COUNT(*) FROM analytics_events e WHERE e.user_id = u.id) AS action_count
            FROM users u
            ORDER BY u.id ASC
            """
        )
        return [dict(r) for r in cur.fetchall()]


def ensure_admin(login: str, password_hash: str) -> None:
    with db.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE username = ?", (login,))
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE users SET password_hash = ?, role = 'admin' WHERE id = ?",
                (password_hash, row["id"]),
            )
        else:
            cur.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'admin')",
                (login, password_hash),
            )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
