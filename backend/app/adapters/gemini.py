from __future__ import annotations

import os

import requests

from ._json import parse_llm_response


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
GEMINI_DEFAULT_MODEL = "gemini-1.5-flash"


def is_available() -> bool:
    return bool(os.getenv("GEMINI_API_KEY", "").strip())


def get_status() -> dict:
    return {
        "key_present": is_available(),
        "model": GEMINI_DEFAULT_MODEL,
        "active_mode": "gemini" if is_available() else "disabled",
    }


def complete_json(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 800,
    temperature: float = 0.1,
) -> dict | None:
    return _call(system_prompt, user_prompt, max_tokens=max_tokens, temperature=temperature)


def _call(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 800,
    temperature: float = 0.1,
) -> dict | None:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    payload = {
        "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }
    try:
        response = requests.post(
            GEMINI_URL,
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        content = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return parse_llm_response(content)
    except Exception:
        return None
