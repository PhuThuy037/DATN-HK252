from __future__ import annotations

from typing import Any, Optional

import httpx

from app.core.config import get_settings
from .base import ChatProvider


class GroqProvider(ChatProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.groq_base_url.rstrip("/")
        self.default_model = settings.groq_model
        self.api_key = (settings.groq_api_key or "").strip()

    async def generate(
        self,
        *,
        system_prompt: Optional[str],
        user_message: str,
        temperature: float = 0.7,
        model_name: Optional[str] = None,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("Groq API key missing")

        model = (model_name or self.default_model).strip()
        messages: list[dict[str, Any]] = []
        if (system_prompt or "").strip():
            messages.append({"role": "system", "content": (system_prompt or "").strip()})
        messages.append({"role": "user", "content": user_message.strip()})

        async with httpx.AsyncClient(base_url=self.base_url, timeout=15) as client:
            r = await client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": float(temperature),
                    "stream": False,
                },
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()

        try:
            content = (
                data.get("choices", [])[0]
                .get("message", {})
                .get("content", "")
            )
        except Exception as exc:
            raise RuntimeError("Groq empty response") from exc

        text = str(content or "").strip()
        if not text:
            raise RuntimeError("Groq empty response")
        return text
