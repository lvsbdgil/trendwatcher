from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException

from ..pipeline.errors import AnalysisPipelineError, error_payload


def http_error(
    status_code: int,
    code: str,
    message: str = "",
    *,
    request_id: str | None = None,
    step: int | None = None,
    step_name: str | None = None,
    details: dict | None = None,
) -> NoReturn:
    raise HTTPException(
        status_code=status_code,
        detail=error_payload(code, message, request_id=request_id,
                             step=step, step_name=step_name, details=details),
    )


def handle_pipeline_error(exc: AnalysisPipelineError) -> NoReturn:
    status_code = 422 if exc.code in {"NO_VALID_ARTICLES", "NO_URLS_FOUND"} else 500
    http_error(
        status_code, exc.code, str(exc),
        request_id=exc.request_id, step=exc.step, step_name=exc.step_name,
    )
