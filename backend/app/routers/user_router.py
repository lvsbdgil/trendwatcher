"""User profile, activity history, password change, day streak."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from .. import analytics
from ..auth import hash_password, verify_password
from ..deps import require_auth
from ..repositories import events as events_repo
from ..repositories import users as users_repo


router = APIRouter(prefix="/api/user", tags=["user"])

PRODUCT_ACTIONS: tuple[str, ...] = (
    "use_test_dataset",
    "use_firecrawl",
    "use_custom_sources",
    "use_custom_text",
    "use_external_fetch",
    "generate_digest",
    "export_digest",
    "save_digest",
)

STREAK_WINDOW_DAYS = 7


def _err(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"ok": False, "error": code, "message": message},
    )


def _compute_streak(user_id: int) -> dict:
    counts = events_repo.user_product_days(user_id, PRODUCT_ACTIONS)
    active_dates = set(counts.keys())

    today = datetime.now(timezone.utc).date()
    today_str = today.isoformat()
    yesterday_str = (today - timedelta(days=1)).isoformat()

    active_today = today_str in active_dates

    if active_today:
        anchor = today
    elif yesterday_str in active_dates:
        anchor = today - timedelta(days=1)
    else:
        anchor = None

    current = 0
    if anchor is not None:
        d = anchor
        while d.isoformat() in active_dates:
            current += 1
            d -= timedelta(days=1)

    best = 0
    if active_dates:
        sorted_days = sorted(date.fromisoformat(s) for s in active_dates)
        run = 1
        best = 1
        for prev, nxt in zip(sorted_days, sorted_days[1:]):
            if (nxt - prev).days == 1:
                run += 1
                best = max(best, run)
            else:
                run = 1

    days: list[dict] = []
    for offset in range(STREAK_WINDOW_DAYS - 1, -1, -1):
        d = today - timedelta(days=offset)
        ds = d.isoformat()
        days.append({
            "date": ds,
            "active": ds in active_dates,
            "count": counts.get(ds, 0),
            "isToday": d == today,
        })

    return {
        "current": current,
        "best": best,
        "activeToday": active_today,
        "lastActiveDate": max(active_dates) if active_dates else None,
        "days": days,
    }


@router.get("/profile")
def get_profile(request: Request, user=Depends(require_auth)):
    record = users_repo.find_by_id(user["id"])
    if not record:
        raise _err(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", "Пользователь не найден.")

    analytics.log_event(
        request, action="profile_opened", mode="auth",
        feature="profile", status="success", user=user,
    )

    streak = _compute_streak(user["id"])
    stats = events_repo.user_stats(user["id"])
    stats["currentStreak"] = streak["current"]
    stats["bestStreak"] = streak["best"]

    return {
        "ok": True,
        "user": {
            "id": record["id"],
            "username": record["username"],
            "role": record["role"],
            "created_at": record["created_at"],
            "last_login_at": record["last_login_at"],
            "last_seen_at": record["last_seen_at"],
        },
        "stats": stats,
        "streak": streak,
        "recentEvents": events_repo.user_recent_events(user["id"], PRODUCT_ACTIONS, limit=5),
    }


@router.get("/events")
def get_events(
    request: Request,
    user=Depends(require_auth),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    total, event_rows = events_repo.user_events_paginated(
        user["id"], PRODUCT_ACTIONS, limit, offset
    )
    return {"ok": True, "total": total, "limit": limit, "offset": offset, "events": event_rows}


class ChangePasswordPayload(BaseModel):
    oldPassword: str = Field(..., min_length=1, max_length=512)
    newPassword: str = Field(..., min_length=1, max_length=512)


@router.post("/change-password")
def change_password(
    payload: ChangePasswordPayload, request: Request, user=Depends(require_auth)
):
    current_hash = users_repo.get_password_hash(user["id"])
    if not current_hash or not verify_password(payload.oldPassword, current_hash):
        analytics.log_event(request, action="error_event", mode="auth",
                            feature="profile", status="fail", user=user,
                            metadata={"reason": "bad_old_password"})
        raise _err(status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS",
                   "Неверный текущий пароль.")

    users_repo.update_password(user["id"], hash_password(payload.newPassword))
    analytics.log_event(request, action="profile_password_changed",
                        mode="auth", feature="profile", status="success", user=user)
    return {"ok": True}
