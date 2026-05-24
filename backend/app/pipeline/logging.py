from __future__ import annotations

import json
import logging
import os
import sys
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any


LOGGER = logging.getLogger("trendwatcher.analysis")


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


_SECRET_KEYS = {"api_key", "apikey", "authorization", "token", "secret", "password"}


def _scrub(value: Any) -> Any:
    """Strip obvious secrets from log payloads."""
    if isinstance(value, dict):
        return {
            k: ("***" if k.lower() in _SECRET_KEYS else _scrub(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_scrub(v) for v in value]
    if isinstance(value, str) and len(value) > 600:
        return value[:600] + "...(truncated)"
    return value


def _format_kv(fields: dict) -> str:
    parts = []
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            try:
                rendered = json.dumps(_scrub(value), ensure_ascii=False, default=str)
            except TypeError:
                rendered = str(value)
        else:
            rendered = str(value)
        if " " in rendered and not (rendered.startswith("\"") or rendered.startswith("{") or rendered.startswith("[")):
            rendered = f"\"{rendered}\""
        parts.append(f"{key}={rendered}")
    return " ".join(parts)


def console_step(request_id: str, step: str, status: str, **fields: Any) -> None:
    """Print canonical `[analysis:<rid>] step=<name> <status> ...` line to stderr.

    Bypasses the logging system so it shows up even when uvicorn's root logger
    is configured in an unexpected way. Always safe to call.
    """
    line = f"[analysis:{request_id or '?'}] step={step} {status}"
    payload = _format_kv(_scrub(fields))
    if payload:
        line = f"{line} {payload}"
    try:
        print(line, file=sys.stderr, flush=True)
    except Exception:  # pragma: no cover — never let logging break the request
        pass


def console_error(request_id: str, step: str, exc: BaseException, **fields: Any) -> None:
    """Print the full error name / message / stack with requestId context."""
    name = type(exc).__name__
    message = str(exc) or "<no message>"
    stack = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    header = f"[analysis:{request_id or '?'}] step={step} error"
    extras = _format_kv({"name": name, **_scrub(fields)})
    try:
        print(f"{header} {extras}".rstrip(), file=sys.stderr, flush=True)
        print(f"[analysis:{request_id or '?'}] step={step} error.message={message}", file=sys.stderr, flush=True)
        print(f"[analysis:{request_id or '?'}] step={step} error.stack:\n{stack}", file=sys.stderr, flush=True)
    except Exception:  # pragma: no cover
        pass


def is_dev_mode() -> bool:
    value = (
        os.getenv("APP_ENV")
        or os.getenv("ENV")
        or os.getenv("FASTAPI_ENV")
        or os.getenv("NODE_ENV")
        or "development"
    )
    return value.lower() not in {"prod", "production"}


def _compact(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        return str(value)


@dataclass
class AnalysisLogger:
    request_id: str
    query: str = ""
    limit: int | None = None
    user_id: int | str | None = None
    enabled: bool = field(default_factory=is_dev_mode)

    def info(self, event: str, **fields: Any) -> None:
        if not self.enabled:
            return
        data = {
            "request_id": self.request_id,
            "event": event,
            "query": self.query,
            "limit": self.limit,
            "user_id": self.user_id,
            **{key: value for key, value in fields.items() if value is not None},
        }
        LOGGER.info("[analysis] %s", _compact(data))

    def step_started(self, step: int, name: str, **fields: Any) -> None:
        self.info("step_started", step=step, step_name=name, **fields)
        console_step(self.request_id, name, "started", **fields)

    def step_completed(self, step: int, name: str, **fields: Any) -> None:
        self.info("step_completed", step=step, step_name=name, **fields)
        console_step(self.request_id, name, "completed", **fields)

    def error(self, code: str, exc: BaseException | None = None, **fields: Any) -> None:
        payload = {
            "code": code,
            **fields,
        }
        if exc is not None:
            payload["error"] = str(exc)
            payload["stack"] = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        if self.enabled:
            self.info("error", **payload)
        # Console error is always emitted so prod-on-dev debugging works too.
        if exc is not None:
            step_label = fields.get("step_name") or fields.get("step") or "unknown"
            extra = {k: v for k, v in fields.items() if k not in {"step_name", "step"}}
            console_error(self.request_id, str(step_label), exc, code=code, **extra)


def configure_analysis_logging() -> None:
    if LOGGER.handlers:
        return
    logging.basicConfig(level=logging.INFO)
