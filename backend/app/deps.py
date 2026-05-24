"""FastAPI dependencies for auth gating."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from .auth import get_current_user


def current_user_or_none(request: Request) -> dict | None:
    return get_current_user(request)


def require_auth(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "ok": False,
                "error": "AUTH_REQUIRED",
                "message": "Войдите или создайте аккаунт.",
            },
        )
    return user


def require_admin(user: dict = Depends(require_auth)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "ok": False,
                "error": "ADMIN_REQUIRED",
                "message": "Доступ только для администраторов.",
            },
        )
    return user
