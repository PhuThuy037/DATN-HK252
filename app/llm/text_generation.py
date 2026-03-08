from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import re
import time
from typing import Any

import httpx

from app.core.config import get_settings


GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LlmTextResult:
    text: str
    provider: str
    model: str
    fallback_used: bool = False


def _normalize_provider(value: str | None) -> str:
    p = (value or "").strip().lower()
    if p in {"gemini", "ollama"}:
        return p
    return "ollama"


def _has_usable_gemini_key(key: str | None) -> bool:
    v = (key or "").strip()
    if not v:
        return False
    lowered = v.lower()
    if lowered in {"x", "changeme", "change-me", "your_api_key"}:
        return False
    return True


def _extract_gemini_text(data: dict[str, Any]) -> str:
    candidates = list(data.get("candidates") or [])
    if not candidates:
        raise RuntimeError(f"Gemini empty candidates: {data}")
    content = candidates[0].get("content") or {}
    parts = list(content.get("parts") or [])
    texts = [str(p.get("text") or "").strip() for p in parts if isinstance(p, dict)]
    out = "\n".join([t for t in texts if t]).strip()
    if not out:
        raise RuntimeError(f"Gemini empty text: {data}")
    return out


def _parse_seconds(text: str) -> float | None:
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*s", str(text or "").lower())
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def _extract_retry_delay_seconds(error_payload: Any) -> float | None:
    try:
        err = error_payload.get("error") if isinstance(error_payload, dict) else None
        details = list((err or {}).get("details") or [])
        for d in details:
            if not isinstance(d, dict):
                continue
            t = str(d.get("@type") or "")
            if "RetryInfo" not in t:
                continue
            delay = d.get("retryDelay")
            if isinstance(delay, str):
                parsed = _parse_seconds(delay)
                if parsed is not None:
                    return parsed
        msg = str((err or {}).get("message") or "")
        parsed = _parse_seconds(msg)
        if parsed is not None:
            return parsed
    except Exception:
        return None
    return None


def _bounded_retry_delay_s(v: float | None, *, default_s: float = 3.0) -> float:
    if v is None:
        return default_s
    return max(0.5, min(20.0, float(v)))


def _build_attempt_chain(preferred: str, *, gemini_available: bool) -> list[str]:
    if preferred == "gemini":
        if gemini_available:
            return ["gemini", "ollama"]
        return ["ollama"]
    return ["ollama"]


def _call_ollama_sync(
    *,
    prompt: str,
    system_prompt: str | None,
    model_name: str | None,
    timeout_s: float,
) -> tuple[str, str]:
    settings = get_settings()
    model = (model_name or settings.ollama_model).strip()
    final_prompt = ""
    if (system_prompt or "").strip():
        final_prompt += (system_prompt or "").strip() + "\n\n"
    final_prompt += prompt.strip()

    with httpx.Client(
        base_url=settings.ollama_base_url.rstrip("/"),
        timeout=timeout_s,
    ) as client:
        r = client.post(
            "/api/generate",
            json={
                "model": model,
                "prompt": final_prompt,
                "stream": False,
                "options": {"temperature": 0},
            },
        )
        r.raise_for_status()
        data: dict[str, Any] = r.json()
    text = str(data.get("response") or "").strip()
    if not text:
        raise RuntimeError("Ollama empty response")
    return text, model


def _call_gemini_sync(
    *,
    prompt: str,
    system_prompt: str | None,
    model_name: str | None,
    timeout_s: float,
    fast_fallback: bool = False,
) -> tuple[str, str]:
    settings = get_settings()
    model = (model_name or settings.gemini_model).strip()
    key = (settings.google_api_key or "").strip()
    if not _has_usable_gemini_key(key):
        raise RuntimeError("Gemini API key missing")

    contents: list[dict[str, Any]] = []
    if (system_prompt or "").strip():
        contents.append({"role": "user", "parts": [{"text": (system_prompt or "").strip()}]})
    contents.append({"role": "user", "parts": [{"text": prompt.strip()}]})

    max_attempts = 1 if fast_fallback else 2
    with httpx.Client(timeout=timeout_s) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                r = client.post(
                    f"{GEMINI_BASE_URL}/models/{model}:generateContent",
                    params={"key": key},
                    json={
                        "contents": contents,
                        "generationConfig": {"temperature": 0},
                    },
                )
                if r.status_code == 429 and attempt < max_attempts:
                    retry_hint = None
                    try:
                        retry_hint = _extract_retry_delay_seconds(r.json())
                    except Exception:
                        retry_hint = None
                    delay_s = _bounded_retry_delay_s(retry_hint)
                    logger.warning(
                        "llm.gemini.sync.rate_limited model=%s attempt=%s retry_after_s=%.2f",
                        model,
                        attempt,
                        delay_s,
                    )
                    time.sleep(delay_s)
                    continue
                r.raise_for_status()
                data: dict[str, Any] = r.json()
                break
            except httpx.ReadTimeout:
                if attempt < max_attempts:
                    logger.warning(
                        "llm.gemini.sync.read_timeout model=%s attempt=%s retry_after_s=1.00",
                        model,
                        attempt,
                    )
                    time.sleep(1.0)
                    continue
                raise
        else:
            raise RuntimeError("Gemini request failed after retries")
    return _extract_gemini_text(data), model


async def _call_ollama_async(
    *,
    prompt: str,
    system_prompt: str | None,
    model_name: str | None,
    timeout_s: float,
) -> tuple[str, str]:
    settings = get_settings()
    model = (model_name or settings.ollama_model).strip()
    final_prompt = ""
    if (system_prompt or "").strip():
        final_prompt += (system_prompt or "").strip() + "\n\n"
    final_prompt += prompt.strip()

    async with httpx.AsyncClient(
        base_url=settings.ollama_base_url.rstrip("/"),
        timeout=timeout_s,
    ) as client:
        r = await client.post(
            "/api/generate",
            json={
                "model": model,
                "prompt": final_prompt,
                "stream": False,
                "options": {"temperature": 0},
            },
        )
        r.raise_for_status()
        data: dict[str, Any] = r.json()
    text = str(data.get("response") or "").strip()
    if not text:
        raise RuntimeError("Ollama empty response")
    return text, model


async def _call_gemini_async(
    *,
    prompt: str,
    system_prompt: str | None,
    model_name: str | None,
    timeout_s: float,
    fast_fallback: bool = False,
) -> tuple[str, str]:
    settings = get_settings()
    model = (model_name or settings.gemini_model).strip()
    key = (settings.google_api_key or "").strip()
    if not _has_usable_gemini_key(key):
        raise RuntimeError("Gemini API key missing")

    contents: list[dict[str, Any]] = []
    if (system_prompt or "").strip():
        contents.append({"role": "user", "parts": [{"text": (system_prompt or "").strip()}]})
    contents.append({"role": "user", "parts": [{"text": prompt.strip()}]})

    max_attempts = 1 if fast_fallback else 2
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                r = await client.post(
                    f"{GEMINI_BASE_URL}/models/{model}:generateContent",
                    params={"key": key},
                    json={
                        "contents": contents,
                        "generationConfig": {"temperature": 0},
                    },
                )
                if r.status_code == 429 and attempt < max_attempts:
                    retry_hint = None
                    try:
                        retry_hint = _extract_retry_delay_seconds(r.json())
                    except Exception:
                        retry_hint = None
                    delay_s = _bounded_retry_delay_s(retry_hint)
                    logger.warning(
                        "llm.gemini.async.rate_limited model=%s attempt=%s retry_after_s=%.2f",
                        model,
                        attempt,
                        delay_s,
                    )
                    await asyncio.sleep(delay_s)
                    continue
                r.raise_for_status()
                data: dict[str, Any] = r.json()
                break
            except httpx.ReadTimeout:
                if attempt < max_attempts:
                    logger.warning(
                        "llm.gemini.async.read_timeout model=%s attempt=%s retry_after_s=1.00",
                        model,
                        attempt,
                    )
                    await asyncio.sleep(1.0)
                    continue
                raise
        else:
            raise RuntimeError("Gemini async request failed after retries")
    return _extract_gemini_text(data), model


def generate_text_sync(
    *,
    prompt: str,
    system_prompt: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    timeout_s: float | None = None,
    fast_fallback: bool = False,
) -> LlmTextResult:
    settings = get_settings()
    preferred = _normalize_provider(provider or settings.non_embedding_llm_provider)
    chain = _build_attempt_chain(
        preferred,
        gemini_available=_has_usable_gemini_key(settings.google_api_key),
    )
    timeout_value = float(timeout_s or settings.non_embedding_llm_timeout_seconds)

    last_exc: Exception | None = None
    for idx, p in enumerate(chain):
        model_for_attempt = model_name if idx == 0 else None
        try:
            if p == "gemini":
                text, model = _call_gemini_sync(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    model_name=model_for_attempt,
                    timeout_s=timeout_value,
                    fast_fallback=fast_fallback,
                )
            else:
                text, model = _call_ollama_sync(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    model_name=model_for_attempt,
                    timeout_s=timeout_value,
                )
            logger.info(
                "llm.generate.sync.success provider=%s model=%s fallback_used=%s preferred=%s",
                p,
                model,
                idx > 0,
                preferred,
            )
            return LlmTextResult(
                text=text,
                provider=p,
                model=model,
                fallback_used=idx > 0,
            )
        except Exception as e:
            logger.warning(
                "llm.generate.sync.attempt_failed provider=%s preferred=%s error=%s",
                p,
                preferred,
                e.__class__.__name__,
            )
            last_exc = e
            continue

    raise RuntimeError("No LLM provider available") from last_exc


async def generate_text_async(
    *,
    prompt: str,
    system_prompt: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    timeout_s: float | None = None,
    fast_fallback: bool = False,
) -> LlmTextResult:
    settings = get_settings()
    preferred = _normalize_provider(provider or settings.non_embedding_llm_provider)
    chain = _build_attempt_chain(
        preferred,
        gemini_available=_has_usable_gemini_key(settings.google_api_key),
    )
    timeout_value = float(timeout_s or settings.non_embedding_llm_timeout_seconds)

    last_exc: Exception | None = None
    for idx, p in enumerate(chain):
        model_for_attempt = model_name if idx == 0 else None
        try:
            if p == "gemini":
                text, model = await _call_gemini_async(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    model_name=model_for_attempt,
                    timeout_s=timeout_value,
                    fast_fallback=fast_fallback,
                )
            else:
                text, model = await _call_ollama_async(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    model_name=model_for_attempt,
                    timeout_s=timeout_value,
                )
            logger.info(
                "llm.generate.async.success provider=%s model=%s fallback_used=%s preferred=%s",
                p,
                model,
                idx > 0,
                preferred,
            )
            return LlmTextResult(
                text=text,
                provider=p,
                model=model,
                fallback_used=idx > 0,
            )
        except Exception as e:
            logger.warning(
                "llm.generate.async.attempt_failed provider=%s preferred=%s error=%s",
                p,
                preferred,
                e.__class__.__name__,
            )
            last_exc = e
            continue

    raise RuntimeError("No LLM provider available") from last_exc
