from __future__ import annotations

from typing import Optional

import httpx

from app.core.config import get_settings
from .base import ChatProvider


class OllamaProvider(ChatProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.default_model = settings.ollama_model  # default

    async def generate(
        self,
        *,
        system_prompt: Optional[str],
        user_message: str,
        temperature: float = 0.7,
        model_name: Optional[str] = None,  # ✅ add
    ) -> str:
        model = (model_name or self.default_model).strip()

        prompt = ""
        if system_prompt:
            prompt += system_prompt.strip() + "\n\n"
        prompt += user_message.strip()

        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=15,
        ) as client:
            r = await client.post(
                "/api/generate",
                json={
                    "model": model,  # ✅ use dynamic model
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": float(temperature)},
                },
            )
            r.raise_for_status()
            data = r.json()

        return (data.get("response") or "").strip()