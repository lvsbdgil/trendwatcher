from __future__ import annotations

from .. import db


def check_and_record(ip: str, window_seconds: int, max_attempts: int) -> bool:
    """Returns True if the request is allowed, False if it is rate-limited."""
    with db.cursor() as cur:
        cur.execute(
            "DELETE FROM auth_rate_limit WHERE attempt_at < datetime('now', ?)",
            (f"-{window_seconds} seconds",),
        )
        cur.execute("SELECT COUNT(*) AS c FROM auth_rate_limit WHERE ip = ?", (ip,))
        if cur.fetchone()["c"] >= max_attempts:
            return False
        cur.execute("INSERT INTO auth_rate_limit (ip) VALUES (?)", (ip,))
    return True
