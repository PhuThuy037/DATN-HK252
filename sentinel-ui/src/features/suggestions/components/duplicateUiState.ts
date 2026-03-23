type DuplicateLevel = "none" | "weak" | "strong";

export type DuplicateUiState = "NO_DUPLICATE" | "NEAR_DUPLICATE" | "EXACT_DUPLICATE";

type ResolveDuplicateUiStateInput = {
  decision?: string | null;
  level?: DuplicateLevel | null;
  candidatesCount?: number;
  topSimilarity?: number | null;
};

function normalizeDecision(decision?: string | null) {
  return String(decision ?? "").trim().toUpperCase();
}

export function resolveDuplicateUiState({
  decision,
  level,
  candidatesCount = 0,
  topSimilarity,
}: ResolveDuplicateUiStateInput): DuplicateUiState {
  const normalizedDecision = normalizeDecision(decision);

  if (normalizedDecision === "EXACT_DUPLICATE" || normalizedDecision === "IDENTICAL") {
    return "EXACT_DUPLICATE";
  }

  if (normalizedDecision === "NEAR_DUPLICATE" || normalizedDecision === "SIMILAR") {
    return "NEAR_DUPLICATE";
  }

  if (
    normalizedDecision === "NO_DUPLICATE" ||
    normalizedDecision === "DIFFERENT" ||
    normalizedDecision === "NONE"
  ) {
    return "NO_DUPLICATE";
  }

  if (typeof topSimilarity === "number" && !Number.isNaN(topSimilarity) && topSimilarity >= 0.99) {
    return "EXACT_DUPLICATE";
  }

  if (level === "strong" && candidatesCount > 0) {
    return "NEAR_DUPLICATE";
  }

  if (level === "weak") {
    return "NEAR_DUPLICATE";
  }

  return "NO_DUPLICATE";
}

