import re
from dataclasses import dataclass
from typing import List


@dataclass
class InjectionResult:
    decision: str
    score: float
    reason: str
    prompt_injection: bool


class SecurityInjectionDetector:
    def __init__(self):
        self.patterns = [
            r"ignore\s+(all\s+)?previous\s+instructions",
            r"reveal\s+(the\s+)?system\s+prompt",
            r"bypass\s+(all\s+)?(policy|policies|guardrails|safety)",
            r"you\s+are\s+dan",
            r"act\s+as\s+an?\s+unrestricted",
            r"print\s+.*(api\s*key|secret|token|env)",
            r"show\s+hidden\s+(rules|policies)",
        ]

    def scan(self, text: str) -> InjectionResult:
        text_lower = text.lower()

        score = 0.0
        matches: List[str] = []

        for pattern in self.patterns:
            if re.search(pattern, text_lower):
                score += 0.3
                matches.append(pattern)

        score = min(score, 1.0)

        if score >= 0.6:
            return InjectionResult(
                decision="BLOCK",
                score=score,
                reason="High confidence prompt injection",
                prompt_injection=True,
            )

        if score >= 0.3:
            return InjectionResult(
                decision="REVIEW",
                score=score,
                reason="Suspicious injection pattern",
                prompt_injection=False,
            )

        return InjectionResult(
            decision="ALLOW",
            score=0.0,
            reason="No injection detected",
            prompt_injection=False,
        )