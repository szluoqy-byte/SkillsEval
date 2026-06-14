from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from .db import connect, row_to_dict


PROVIDER_TYPES = {"openai_compatible", "anthropic"}


@dataclass
class ModelCallResult:
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    raw_usage: dict[str, Any] | None = None
    error: str = ""


def normalize_base_url(value: str) -> str:
    cleaned = value.strip().rstrip("/")
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url must be a valid http/https URL.")
    return cleaned


def mask_api_key(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:3]}...{value[-4:]}"


def sanitize_provider(provider: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(provider)
    key = str(sanitized.pop("api_key", "") or "")
    sanitized["api_key_configured"] = bool(key)
    sanitized["api_key_preview"] = mask_api_key(key)
    return sanitized


def get_role_model(role: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT
              m.*,
              p.name AS provider_name,
              p.provider_type,
              p.base_url,
              p.api_key,
              p.enabled AS provider_enabled
            FROM model_role_settings rs
            JOIN model_api_models m ON m.id = rs.model_api_model_id
            JOIN model_api_providers p ON p.id = m.provider_id
            WHERE rs.role = ?
            """,
            (role,),
        ).fetchone()
        return row_to_dict(row) if row else None


def call_configured_model(model: dict[str, Any], prompt: str, timeout_seconds: int = 60) -> ModelCallResult:
    if not model:
        return ModelCallResult(content="", error="Model is not configured.")
    if not bool(model.get("enabled")):
        return ModelCallResult(content="", error="Configured model is disabled.")
    if not bool(model.get("provider_enabled")):
        return ModelCallResult(content="", error="Configured model provider is disabled.")
    provider_type = str(model.get("provider_type") or "")
    if provider_type not in PROVIDER_TYPES:
        return ModelCallResult(content="", error=f"Unsupported provider_type: {provider_type}")
    api_key = str(model.get("api_key") or "")
    if not api_key:
        return ModelCallResult(content="", error="Configured model provider has no API key.")
    try:
        base_url = normalize_base_url(str(model.get("base_url") or ""))
    except ValueError as error:
        return ModelCallResult(content="", error=str(error))
    model_id = str(model.get("model_id") or "")
    if not model_id:
        return ModelCallResult(content="", error="Configured model has no model_id.")
    if provider_type == "anthropic":
        return call_anthropic(base_url, api_key, model_id, prompt, timeout_seconds)
    return call_openai_compatible(base_url, api_key, model_id, prompt, timeout_seconds)


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout_seconds: int) -> tuple[dict[str, Any] | None, str]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        return None, f"Model API returned HTTP {error.code}: {detail or error.reason}"
    except urllib.error.URLError as error:
        return None, f"Model API request failed: {error.reason}"
    except TimeoutError:
        return None, f"Model API timed out after {timeout_seconds}s."
    except OSError as error:
        return None, f"Model API request failed: {error}"
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as error:
        return None, f"Model API returned non-JSON response: {error}"
    return payload if isinstance(payload, dict) else None, ""


def call_openai_compatible(base_url: str, api_key: str, model_id: str, prompt: str, timeout_seconds: int) -> ModelCallResult:
    payload, error = post_json(
        f"{base_url}/chat/completions",
        {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        },
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        timeout_seconds,
    )
    if error or not payload:
        return ModelCallResult(content="", error=error or "Model API returned an empty response.")
    content = ""
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else {}
        if isinstance(message, dict):
            content = str(message.get("content") or "")
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or input_tokens + output_tokens)
    return ModelCallResult(content=content, input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens, raw_usage=usage)


def call_anthropic(base_url: str, api_key: str, model_id: str, prompt: str, timeout_seconds: int) -> ModelCallResult:
    payload, error = post_json(
        f"{base_url}/v1/messages",
        {
            "model": model_id,
            "max_tokens": 1024,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        },
        {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        timeout_seconds,
    )
    if error or not payload:
        return ModelCallResult(content="", error=error or "Model API returned an empty response.")
    content_parts = payload.get("content") if isinstance(payload.get("content"), list) else []
    text_parts = [str(item.get("text") or "") for item in content_parts if isinstance(item, dict) and item.get("type") == "text"]
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    return ModelCallResult(content="\n".join(text_parts), input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=input_tokens + output_tokens, raw_usage=usage)
