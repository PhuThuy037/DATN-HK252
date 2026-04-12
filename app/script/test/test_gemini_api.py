from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

import httpx


GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def _mask_key(key: str) -> str:
    k = (key or "").strip()
    if len(k) <= 8:
        return "*" * len(k)
    return f"{k[:4]}...{k[-4:]}"


def _extract_text(data: dict[str, Any]) -> str:
    candidates = list(data.get("candidates") or [])
    if not candidates:
        return ""
    content = candidates[0].get("content") or {}
    parts = list(content.get("parts") or [])
    texts = [str(p.get("text") or "").strip() for p in parts if isinstance(p, dict)]
    return "\n".join([t for t in texts if t]).strip()


def run_once(*, model: str, key: str, timeout_s: float, prompt: str) -> tuple[bool, str]:
    url = f"{GEMINI_BASE_URL}/models/{model}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0},
    }

    t0 = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout_s) as client:
            r = client.post(url, params={"key": key}, json=payload)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        print(f"status={r.status_code} elapsed_ms={elapsed_ms}")
        if r.status_code >= 400:
            body = r.text
            if len(body) > 2000:
                body = body[:2000] + "...(truncated)"
            print("error_body=", body)
            return False, f"http_{r.status_code}"

        data = r.json()
        text = _extract_text(data)
        print("response_text=", text[:500] if text else "(empty)")
        return True, "ok"
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        print(f"exception={e.__class__.__name__} elapsed_ms={elapsed_ms} detail={e!r}")
        return False, e.__class__.__name__


def main() -> int:
    parser = argparse.ArgumentParser(description="Direct Gemini API connectivity test")
    parser.add_argument("--model", default=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview"))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("NON_EMBEDDING_LLM_TIMEOUT_SECONDS", "12")))
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument(
        "--prompt",
        default="Return JSON only: {\"ok\":true,\"source\":\"gemini_test\"}",
    )
    args = parser.parse_args()

    key = (os.getenv("GOOGLE_API_KEY") or "").strip()
    if not key:
        print("GOOGLE_API_KEY is empty")
        return 2

    print(
        json.dumps(
            {
                "model": args.model,
                "timeout_s": args.timeout,
                "attempts": args.attempts,
                "api_key_masked": _mask_key(key),
            },
            ensure_ascii=False,
        )
    )

    ok_count = 0
    fail_reasons: list[str] = []
    for i in range(1, max(1, int(args.attempts)) + 1):
        print(f"\n--- attempt {i} ---")
        ok, reason = run_once(
            model=args.model,
            key=key,
            timeout_s=float(args.timeout),
            prompt=args.prompt,
        )
        if ok:
            ok_count += 1
        else:
            fail_reasons.append(reason)

    print(
        json.dumps(
            {
                "ok_count": ok_count,
                "total": max(1, int(args.attempts)),
                "fail_reasons": fail_reasons,
            },
            ensure_ascii=False,
        )
    )
    return 0 if ok_count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
