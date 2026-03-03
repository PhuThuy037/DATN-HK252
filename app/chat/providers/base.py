from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional


class ChatProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        *,
        system_prompt: Optional[str],
        user_message: str,
        temperature: float = 0.7,
        model_name: Optional[str] = None,
    ) -> str:
        ...