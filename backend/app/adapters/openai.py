from __future__ import annotations

import os

import requests

from ._json import parse_llm_response


OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"


def get_providers() -> list[dict]:
    """Return all configured providers in failover order (OpenRouter → OpenAI)."""
    providers = []
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if openrouter_key:
        providers.append({
            "api_key": openrouter_key,
            "model": os.getenv("OPENROUTER_MODEL", "").strip() or "openai/gpt-4o-mini",
            "url": os.getenv("OPENROUTER_URL", "").strip() or OPENROUTER_URL,
            "provider": "openrouter",
        })
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key:
        providers.append({
            "api_key": openai_key,
            "model": os.getenv("OPENAI_MODEL", "").strip() or OPENAI_DEFAULT_MODEL,
            "url": OPENAI_URL,
            "provider": "openai",
        })
    return providers


def get_settings() -> dict:
    providers = get_providers()
    if providers:
        return providers[0]
    return {"api_key": "", "model": OPENAI_DEFAULT_MODEL, "url": OPENAI_URL, "provider": "openai"}


def is_available() -> bool:
    return bool(get_providers())


def get_status() -> dict:
    providers = get_providers()
    primary = providers[0] if providers else {"provider": "openai", "model": OPENAI_DEFAULT_MODEL}
    return {
        "provider": primary.get("provider"),
        "key_present": bool(providers),
        "model": primary.get("model"),
        "llm_enabled": bool(providers),
        "active_mode": primary.get("provider") if providers else "local_fallback",
        "fallback_providers": [p["provider"] for p in providers[1:]],
    }


def complete_json(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1000,
    temperature: float = 0.1,
) -> dict | None:
    providers = get_providers()
    if not providers:
        return None

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    last_error = None
    for provider_index, settings in enumerate(providers):
        for attempt in range(2):
            try:
                response = _call(settings, messages, max_tokens, temperature)
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                parsed = parse_llm_response(content)
                if parsed is not None:
                    return parsed
                _log_parse_failure(content)
            except requests.HTTPError as exc:
                status = getattr(exc.response, "status_code", None)
                last_error = exc
                _log_request_failure(exc, provider=settings["provider"], status=status)
                if status and status < 500 and status not in (408, 429):
                    break
            except Exception as exc:
                last_error = exc
                _log_request_failure(exc, provider=settings["provider"])
                break

            if attempt == 0:
                messages.append({
                    "role": "user",
                    "content": (
                        "Предыдущий ответ не был валидным JSON. Верни только один JSON-объект без markdown, "
                        "комментариев и пояснений. Не добавляй факты вне входного текста."
                    ),
                })

        if provider_index + 1 < len(providers):
            next_provider = providers[provider_index + 1]
            _log_failover(settings["provider"], next_provider["provider"], last_error)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

    return None


def _call(settings: dict, messages: list, max_tokens: int, temperature: float) -> requests.Response:
    headers = {
        "Authorization": f"Bearer {settings['api_key']}",
        "Content-Type": "application/json",
    }
    if settings["provider"] == "openrouter":
        headers["HTTP-Referer"] = os.getenv("APP_PUBLIC_URL", "http://localhost")
        headers["X-Title"] = "TrendWatcher"
    return requests.post(
        settings["url"],
        headers=headers,
        json={
            "model": settings["model"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        },
        timeout=30,
    )


def _dev_log_enabled() -> bool:
    value = os.getenv("APP_ENV") or os.getenv("ENV") or "development"
    return value.lower() not in {"prod", "production"}


def _log_parse_failure(raw: str) -> None:
    if _dev_log_enabled():
        print("[analysis llm] code=LLM_JSON_PARSE_FAILED raw_response=" + str(raw or "")[:4000])


def _log_request_failure(exc: Exception, *, provider: str | None = None, status: int | None = None) -> None:
    if not _dev_log_enabled():
        return
    extras = []
    if provider:
        extras.append(f"provider={provider}")
    if status is not None:
        extras.append(f"status={status}")
    suffix = " " + " ".join(extras) if extras else ""
    print(f"[analysis llm] code=LLM_REQUEST_FAILED{suffix} error={type(exc).__name__}: {exc}")


def _log_failover(from_provider: str, to_provider: str, exc: Exception | None) -> None:
    if _dev_log_enabled():
        print(
            f"[analysis llm] failover from={from_provider} to={to_provider} "
            f"reason={type(exc).__name__ if exc else 'unknown'}: {exc}"
        )
