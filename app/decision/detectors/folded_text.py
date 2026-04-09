from __future__ import annotations

import unicodedata


def fold_text_with_mapping(text: str) -> tuple[str, list[int]]:
    folded_chars: list[str] = []
    mapping: list[int] = []

    for index, raw_char in enumerate(str(text or "")):
        lowered = raw_char.lower().replace("\u0111", "d")
        normalized = unicodedata.normalize("NFKD", lowered)

        emitted = False
        for char in normalized:
            if unicodedata.combining(char):
                continue
            folded_chars.append(char)
            mapping.append(index)
            emitted = True

        if not emitted:
            folded_chars.append(" ")
            mapping.append(index)

    return "".join(folded_chars), mapping


def original_span_from_folded(
    *,
    mapping: list[int],
    folded_start: int,
    folded_end: int,
    original_length: int,
) -> tuple[int, int]:
    if not mapping:
        return (0, 0)

    safe_start = max(0, min(int(folded_start), len(mapping) - 1))
    safe_end = max(safe_start + 1, min(int(folded_end), len(mapping)))

    original_start = mapping[safe_start]
    original_end = mapping[safe_end - 1] + 1
    original_end = max(original_start + 1, min(original_end, int(original_length)))
    return (original_start, original_end)
