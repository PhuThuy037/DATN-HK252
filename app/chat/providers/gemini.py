from __future__ import annotations

from typing import Optional

import httpx

from app.core.config import get_settings
from .base import ChatProvider


class GeminiProvider(ChatProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.google_api_key
        # default model nếu conversation không truyền model_name
        self.default_model = "gemini-1.5-flash"
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    async def generate(
        self,
        *,
        system_prompt: Optional[str],
        user_message: str,
        temperature: float = 0.7,
        model_name: Optional[str] = None,  # ✅ add
    ) -> str:
        model = (model_name or self.default_model).strip()

        contents: list[dict] = []

        # NOTE: Gemini API cho phép contents nhiều message.
        # MVP: system_prompt đưa như 1 user message ở đầu.
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": system_prompt}]})

        contents.append({"role": "user", "parts": [{"text": user_message}]})

        # timeout 15s đủ dùng; muốn "fail-fast" hơn thì giảm 8-10s.
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{self.base_url}/models/{model}:generateContent",
                params={"key": self.api_key},
                json={
                    "contents": contents,
                    "generationConfig": {"temperature": float(temperature)},
                },
            )
            r.raise_for_status()
            data = r.json()

        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            return "Sorry, I couldn't generate a response."