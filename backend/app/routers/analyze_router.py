"""Analysis endpoints: sample dataset and custom article digest."""
from __future__ import annotations

import logging

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request

from ..config import SAMPLE_DATA_PATH
from ..deps import current_user_or_none, require_auth
from ..pipeline.errors import AnalysisPipelineError
from ..pipeline.logging import console_error, new_request_id
from ..pipeline.runner import run_pipeline
from ..schemas import AnalyzeRequest
from ._errors import handle_pipeline_error, http_error


router = APIRouter(tags=["analyze"])
logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    rid = getattr(getattr(request, "state", None), "request_id", None)
    return rid or new_request_id()


def _user_id(user: dict | None) -> int | None:
    return user.get("id") if isinstance(user, dict) else None


@router.get("/api/sample")
def sample(request: Request):
    if not SAMPLE_DATA_PATH.exists():
        raise HTTPException(status_code=500, detail="Sample data not available")
    try:
        df = pd.read_csv(SAMPLE_DATA_PATH).fillna("")
        return {"articles": df.to_dict(orient="records")}
    except Exception as exc:
        logger.exception("Failed to read sample data: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to read sample data") from exc


@router.post("/api/sample/analyze")
def sample_analyze(request: Request):
    request_id = _request_id(request)
    if not SAMPLE_DATA_PATH.exists():
        raise HTTPException(status_code=500, detail="Sample data file not found")

    try:
        df = pd.read_csv(SAMPLE_DATA_PATH).fillna("")
        articles = df.to_dict(orient="records")
    except Exception as exc:
        logger.exception("Failed to read sample data: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to read sample data") from exc

    user = current_user_or_none(request)

    try:
        result = run_pipeline(
            articles=articles, top_n=5, use_llm=False,
            request_id=request_id, user_id=_user_id(user),
        )
    except AnalysisPipelineError as exc:
        handle_pipeline_error(exc)
    except Exception as exc:
        console_error(request_id, "response", exc, route="/api/sample/analyze")
        logger.exception("Pipeline failed (sample): %s", exc)
        http_error(500, "UNKNOWN_ERROR", f"{type(exc).__name__}: {exc}",
                   request_id=request_id, step=6, step_name="response")

    return result


@router.post("/api/analyze")
def analyze(payload: AnalyzeRequest, request: Request, user: dict = Depends(require_auth)):
    request_id = _request_id(request)
    articles = [
        a.model_dump() if hasattr(a, "model_dump") else a.dict()
        for a in payload.articles
    ]
    if not articles:
        raise HTTPException(status_code=400, detail="Field 'articles' must not be empty")

    try:
        result = run_pipeline(
            articles=articles, top_n=payload.top_n, use_llm=payload.use_llm,
            request_id=request_id, user_id=_user_id(user),
        )
    except AnalysisPipelineError as exc:
        handle_pipeline_error(exc)
    except Exception as exc:
        console_error(request_id, "response", exc, route="/api/analyze",
                      input_count=len(articles), top_n=payload.top_n, use_llm=payload.use_llm)
        logger.exception("Pipeline failed (analyze): %s", exc)
        http_error(500, "UNKNOWN_ERROR", f"{type(exc).__name__}: {exc}",
                   request_id=request_id, step=6, step_name="response")

    return result
