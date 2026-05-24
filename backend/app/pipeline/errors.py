from __future__ import annotations

from dataclasses import dataclass


ERROR_MESSAGES = {
    "FIRECRAWL_API_KEY_MISSING": "Firecrawl API key is not configured.",
    "FIRECRAWL_REQUEST_FAILED": "Firecrawl request failed.",
    "NO_URLS_FOUND": "No suitable publications were found for this query.",
    "EXTRACTION_FAILED": "Could not extract content from the supplied pages.",
    "NO_VALID_ARTICLES": "No valid articles remained after extraction and filtering.",
    "LLM_API_KEY_MISSING": "LLM API key is not configured.",
    "LLM_REQUEST_FAILED": "LLM request failed.",
    "LLM_JSON_PARSE_FAILED": "LLM returned invalid JSON.",
    "SCORING_FAILED": "Scoring failed.",
    "AUTH_REQUIRED": "Authentication is required.",
    "UNKNOWN_ERROR": "Unknown analysis error.",
}


@dataclass
class AnalysisPipelineError(Exception):
    code: str
    message: str = ""
    step: int | None = None
    step_name: str | None = None
    request_id: str | None = None
    partial_result: dict | None = None

    def __str__(self) -> str:
        return self.message or ERROR_MESSAGES.get(self.code, ERROR_MESSAGES["UNKNOWN_ERROR"])


def error_payload(
    code: str,
    message: str | None = None,
    *,
    request_id: str | None = None,
    step: int | None = None,
    step_name: str | None = None,
    details: dict | None = None,
) -> dict:
    payload = {
        "ok": False,
        "error": code,
        "message": message or ERROR_MESSAGES.get(code, ERROR_MESSAGES["UNKNOWN_ERROR"]),
    }
    if request_id:
        payload["request_id"] = request_id
    if step is not None:
        payload["step"] = step
    if step_name:
        payload["step_name"] = step_name
    if details:
        payload["details"] = details
    return payload
