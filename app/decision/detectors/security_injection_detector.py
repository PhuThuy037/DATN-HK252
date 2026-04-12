import re
import unicodedata
from dataclasses import dataclass
from typing import List, Dict, Tuple


@dataclass(slots=True)
class InjectionResult:
    decision: str  # ALLOW | REVIEW | BLOCK
    score: float  # 0..1
    reason: str
    prompt_injection: bool
    categories: List[str]
    matched_rules: List[str]


class SecurityInjectionDetector:
    def __init__(self) -> None:
        # rule: (pattern, weight, category, label)
        self.rules: List[Tuple[str, float, str, str]] = [
            # =========================
            # Override / Jailbreak
            # =========================
            (
                r"\bignore\s+(all\s+)?previous\s+instructions\b",
                0.6,
                "jailbreak",
                "ignore_prev",
            ),
            (
                r"\bdisregard\s+(all\s+)?previous\s+instructions\b",
                0.6,
                "jailbreak",
                "disregard_prev",
            ),
            (
                r"\boverride\s+(all\s+)?previous\s+instructions\b",
                0.7,
                "jailbreak",
                "override_prev",
            ),
            (
                r"\byou\s+are\s+not\s+chatgpt\b",
                0.7,
                "jailbreak",
                "not_chatgpt",
            ),
            (
                r"\byou\s+are\s+dan\b",
                0.7,
                "jailbreak",
                "dan",
            ),
            (
                r"\bdeveloper\s+mode\b",
                0.5,
                "jailbreak",
                "dev_mode",
            ),
            (
                r"\bact\s+as\s+an?\s+(unrestricted|uncensored)\b",
                0.6,
                "jailbreak",
                "unrestricted",
            ),
            (
                r"\bbypass\s+(safety|restrictions|filters)\b",
                0.7,
                "jailbreak",
                "bypass_safety",
            ),
            (
                r"\b(bo\s+qua|bo\s+het|huy\s+bo)\s+(tat\s+ca\s+)?(quy\s+tac|huong\s+dan|chi\s+dan)\s+(truoc\s+do|cu)\b",
                0.6,
                "jailbreak",
                "vi_ignore_prev",
            ),
            (
                r"\b(coi\s+nhu|xem\s+nhu)\s+(tat\s+ca\s+)?(quy\s+tac|huong\s+dan|chi\s+dan)\s+(truoc\s+do|cu)\s+(khong\s+con\s+hieu\s+luc|het\s+hieu\s+luc|vo\s+hieu)\b",
                0.65,
                "jailbreak",
                "vi_prev_invalid",
            ),
            (
                r"\b(tra\s+loi|phan\s+hoi)\s+tu\s+do\b",
                0.3,
                "jailbreak",
                "vi_answer_freely",
            ),
            (
                r"\b(khong\s+can|bo\s+qua)\s+(gioi\s+han|rang\s+buoc|han\s+che|kiem\s+duyet)\b",
                0.35,
                "jailbreak",
                "vi_no_limits",
            ),
            # =========================
            # Prompt / Policy Exfiltration
            # =========================
            (
                r"\breveal\s+(the\s+)?system\s+prompt\b",
                0.9,
                "exfiltration",
                "reveal_system",
            ),
            (
                r"\breveal\s+hidden\s+(instructions|rules|policies)\b",
                0.8,
                "exfiltration",
                "reveal_hidden",
            ),
            (
                r"\b(show|print|dump)\b.*\b(api\s*key|secret|token|env|password)\b",
                0.8,
                "exfiltration",
                "secrets_dump",
            ),
            (
                r"\bprint\s+all\s+environment\s+variables\b",
                0.8,
                "exfiltration",
                "print_env",
            ),
            # =========================
            # RAG abuse
            # =========================
            (
                r"\breturn\s+raw\s+(chunks|documents)\b",
                0.5,
                "rag_abuse",
                "raw_chunks",
            ),
            (
                r"\bdump\s+(your\s+)?memory\b",
                0.6,
                "rag_abuse",
                "dump_memory",
            ),
            (
                r"\bshow\s+all\s+sources\b",
                0.4,
                "rag_abuse",
                "show_sources",
            ),
        ]

        self.block_threshold = 0.85
        self.review_threshold = 0.45

    def _normalize(self, text: str) -> str:
        t = text.lower()

        # remove accents
        t = unicodedata.normalize("NFKD", t)
        t = "".join(ch for ch in t if not unicodedata.combining(ch))

        # remove zero-width chars
        t = re.sub(r"[\u200B-\u200D\uFEFF]", "", t)

        # collapse whitespace
        t = re.sub(r"\s+", " ", t).strip()

        # simple leetspeak
        t = t.translate(
            str.maketrans({"0": "o", "1": "i", "3": "e", "@": "a", "$": "s"})
        )

        return t

    def scan(self, text: str) -> InjectionResult:
        t = self._normalize(text)

        score = 0.0
        cats: Dict[str, float] = {}
        matched_rules: List[str] = []

        for pattern, weight, category, label in self.rules:
            if re.search(pattern, t):
                score += weight
                cats[category] = max(cats.get(category, 0.0), weight)
                matched_rules.append(label)

        score = min(score, 1.0)
        categories = sorted(cats.keys())

        # BLOCK if:
        # - score high
        # - OR exfiltration detected with strong weight
        if score >= self.block_threshold or (
            "exfiltration" in categories and score >= 0.7
        ):
            return InjectionResult(
                decision="BLOCK",
                score=score,
                reason="Prompt injection / exfiltration attempt detected",
                prompt_injection=True,
                categories=categories,
                matched_rules=matched_rules,
            )

        if score >= self.review_threshold:
            return InjectionResult(
                decision="REVIEW",
                score=score,
                reason="Suspicious instruction pattern detected",
                prompt_injection=False,
                categories=categories,
                matched_rules=matched_rules,
            )

        return InjectionResult(
            decision="ALLOW",
            score=score,
            reason="No injection detected",
            prompt_injection=False,
            categories=[],
            matched_rules=[],
        )
