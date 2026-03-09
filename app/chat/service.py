# app/chat/service.py
from __future__ import annotations

from typing import Optional

from app.chat.providers.base import ChatProvider
from app.chat.providers.gemini import GeminiProvider
from app.chat.providers.groq import GroqProvider
from app.chat.providers.ollama import OllamaProvider
from app.core.config import get_settings


def _is_gemini_model(name: Optional[str]) -> bool:
    return bool(name and name.lower().startswith("gemini-"))


def _looks_like_groq_model(name: str) -> bool:
    n = (name or "").strip().lower()
    return n.startswith(("llama-", "mixtral-", "gemma", "deepseek-", "moonshot-"))


def _normalize_chat_provider(value: str | None) -> str:
    p = (value or "").strip().lower()
    if p in {"groq", "gemini", "ollama"}:
        return p
    return "groq"


def _resolve_model_route(model_name: str, default_provider: str) -> tuple[str, str]:
    raw = (model_name or "").strip()
    lowered = raw.lower()

    if lowered.startswith("groq/"):
        return "groq", raw.split("/", 1)[1].strip() or raw
    if lowered.startswith("gemini/"):
        return "gemini", raw.split("/", 1)[1].strip() or raw
    if lowered.startswith("ollama/"):
        return "ollama", raw.split("/", 1)[1].strip() or raw

    if _is_gemini_model(raw):
        return "gemini", raw
    if _looks_like_groq_model(raw):
        return "groq", raw
    return default_provider, raw


class ChatService:
    def __init__(self) -> None:
        settings = get_settings()
        self.primary_name = _normalize_chat_provider(getattr(settings, "chat_provider", "groq"))

        self.providers: dict[str, ChatProvider] = {
            "groq": GroqProvider(),
            "gemini": GeminiProvider(),
            "ollama": OllamaProvider(),
        }
        self.fallback_order = [
            p for p in ("groq", "gemini", "ollama") if p != self.primary_name
        ]

    async def _generate_with_provider(
        self,
        *,
        provider_name: str,
        system_prompt: Optional[str],
        user_message: str,
        temperature: float,
        model_name: Optional[str],
    ) -> str:
        provider = self.providers[provider_name]
        return await provider.generate(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=temperature,
            model_name=model_name,
        )

    async def generate_reply(
        self,
        *,
        system_prompt: Optional[str],
        user_message: str,
        temperature: float = 0.7,
        model_name: Optional[str] = None,
    ) -> str:
        if model_name:
            chosen_provider, routed_model = _resolve_model_route(
                model_name=model_name,
                default_provider=self.primary_name,
            )
            chain = [chosen_provider] + [
                p for p in [self.primary_name, *self.fallback_order] if p != chosen_provider
            ]

            for idx, provider_name in enumerate(chain):
                try:
                    return await self._generate_with_provider(
                        provider_name=provider_name,
                        system_prompt=system_prompt,
                        user_message=user_message,
                        temperature=temperature,
                        model_name=routed_model if idx == 0 else None,
                    )
                except Exception:
                    continue
            return "Service temporarily unavailable."

        chain = [self.primary_name, *self.fallback_order]
        for provider_name in chain:
            try:
                return await self._generate_with_provider(
                    provider_name=provider_name,
                    system_prompt=system_prompt,
                    user_message=user_message,
                    temperature=temperature,
                    model_name=None,
                )
            except Exception:
                continue
        return "Service temporarily unavailable."
