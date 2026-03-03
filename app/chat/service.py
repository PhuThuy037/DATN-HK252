# app/chat/service.py
from __future__ import annotations

from typing import Optional

from app.core.config import get_settings
from app.chat.providers.ollama import OllamaProvider
from app.chat.providers.gemini import GeminiProvider


def _is_gemini_model(name: Optional[str]) -> bool:
    if not name:
        return False
    return name.lower().startswith("gemini-")


class ChatService:
    def __init__(self) -> None:
        settings = get_settings()

        provider = getattr(settings, "chat_provider", "gemini")

        self.gemini = GeminiProvider()
        self.ollama = OllamaProvider()

        if provider == "ollama":
            self.primary = self.ollama
            self.fallback = None
        elif provider == "gemini":
            self.primary = self.gemini
            self.fallback = self.ollama
        else:
            self.primary = self.ollama
            self.fallback = None

    async def generate_reply(
        self,
        *,
        system_prompt: Optional[str],
        user_message: str,
        temperature: float = 0.7,
        model_name: Optional[str] = None,
    ) -> str:
        # 1) If client provided model_name => route by model family
        if model_name:
            chosen = self.gemini if _is_gemini_model(model_name) else self.ollama
            other = self.ollama if chosen is self.gemini else self.gemini

            # Try chosen with model_name
            try:
                return await chosen.generate(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    temperature=temperature,
                    model_name=model_name,
                )
            except Exception:
                # Fallback: try other WITHOUT model_name (avoid passing invalid model)
                try:
                    return await other.generate(
                        system_prompt=system_prompt,
                        user_message=user_message,
                        temperature=temperature,
                        model_name=None,
                    )
                except Exception:
                    return "Service temporarily unavailable."

        # 2) No model_name => keep old behavior (primary/fallback from ENV)
        try:
            return await self.primary.generate(
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=temperature,
                model_name=None,
            )
        except Exception:
            if self.fallback:
                try:
                    return await self.fallback.generate(
                        system_prompt=system_prompt,
                        user_message=user_message,
                        temperature=temperature,
                        model_name=None,
                    )
                except Exception:
                    return "Service temporarily unavailable."
            return "Service temporarily unavailable."