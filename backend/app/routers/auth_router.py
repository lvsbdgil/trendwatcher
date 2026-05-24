"""Authentication endpoints: register / login / logout / me."""
from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from ..auth import (
    clear_session_cookie,
    create_user,
    find_user,
    get_current_user,
    make_token,
    set_session_cookie,
    touch_login,
    verify_password,
)
from ..repositories import rate_limit as rate_limit_repo


router = APIRouter(prefix="/api/auth", tags=["auth"])

_RATE_WINDOW_SECONDS = 60
_RATE_MAX_ATTEMPTS = 15

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.\-]{3,32}$")
MIN_PASSWORD_LEN = 6


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _rate_limit_ok(ip: str) -> bool:
    if not ip:
        return True
    return rate_limit_repo.check_and_record(ip, _RATE_WINDOW_SECONDS, _RATE_MAX_ATTEMPTS)


def _err(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"ok": False, "error": code, "message": message},
    )


class LoginPayload(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=512)


class RegisterPayload(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=512)


@router.post("/register")
def register(payload: RegisterPayload, request: Request, response: Response):
    ip = _client_ip(request)
    if not _rate_limit_ok(ip):
        raise _err(status.HTTP_429_TOO_MANY_REQUESTS, "RATE_LIMITED",
                   "Слишком много попыток. Попробуйте позже.")

    username = payload.username.strip()
    if not USERNAME_RE.match(username):
        raise _err(status.HTTP_400_BAD_REQUEST, "INVALID_USERNAME",
                   "Логин: 3–32 символа, латиница, цифры, _ . -")

    if find_user(username):
        raise _err(status.HTTP_400_BAD_REQUEST, "REGISTRATION_FAILED",
                   "Не удалось создать аккаунт. Попробуйте другой логин.")

    user = create_user(username, payload.password, role="user")
    if not user:
        raise _err(status.HTTP_500_INTERNAL_SERVER_ERROR, "CREATE_FAILED",
                   "Не удалось создать пользователя.")

    token = make_token(user["id"], user["username"], user["role"])
    set_session_cookie(response, token)
    return {"ok": True, "user": user}


@router.post("/login")
def login(payload: LoginPayload, request: Request, response: Response):
    ip = _client_ip(request)
    if not _rate_limit_ok(ip):
        raise _err(status.HTTP_429_TOO_MANY_REQUESTS, "RATE_LIMITED",
                   "Слишком много попыток. Попробуйте позже.")

    user = find_user(payload.username)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise _err(status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS",
                   "Неверный логин или пароль.")

    token = make_token(user["id"], user["username"], user["role"])
    set_session_cookie(response, token)
    touch_login(user["id"])

    safe_user = {"id": user["id"], "username": user["username"], "role": user["role"]}
    return {"ok": True, "user": safe_user}


@router.post("/logout")
def logout(response: Response):
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    user = get_current_user(request)
    if not user:
        return {"ok": False, "user": None}
    return {
        "ok": True,
        "user": {"id": user["id"], "username": user["username"], "role": user["role"]},
    }
