import { useEffect, useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import type { SuggestionDuplicateCandidate } from "@/features/suggestions/types";
import { Button } from "@/shared/ui/button";
import { DuplicateList } from "@/features/suggestions/components/DuplicateList";
import { Card } from "@/shared/ui/card";
import { resolveDuplicateUiState } from "@/features/suggestions/components/duplicateUiState";

type DuplicateInsight = {
  level?: "none" | "weak" | "strong";
  reason?: string;
  duplicateRisk?: string;
  conflictRisk?: string;
  runtimeUsable?: boolean;
  rationale?: string;
  similarRules?: SuggestionDuplicateCandidate[];
  candidates?: SuggestionDuplicateCandidate[];
};

type SuggestionDuplicateAlertProps = {
  insight?: DuplicateInsight | null;
  onViewRule?: (candidate: SuggestionDuplicateCandidate) => void;
  onCompareRule?: (candidate: SuggestionDuplicateCandidate) => void;
  onContinueToDraft: () => void;
  forceExpand?: boolean;
};

function formatDuplicateReason(reason?: string | null) {
  const text = String(reason ?? "").trim();
  if (!text) {
    return null;
  }

  const normalized = text.toLowerCase();
  if (normalized.includes("semantic_signature_match")) {
    return "Detected via semantic matching";
  }

  // Hide raw internal reason codes (snake_case / code-like tokens).
  if (/^[a-z0-9_]+$/.test(normalized) || normalized.includes("_")) {
    return null;
  }

  return text;
}

export function SuggestionDuplicateAlert({
  insight,
  onViewRule,
  onCompareRule,
  onContinueToDraft,
  forceExpand = false,
}: SuggestionDuplicateAlertProps) {
  if (!insight) {
    return null;
  }

  const candidates = insight.similarRules ?? insight.candidates ?? [];
  const duplicateState = resolveDuplicateUiState({
    decision: insight.duplicateRisk,
    level: insight.level,
    candidatesCount: candidates.length,
    topSimilarity: candidates[0]?.similarity,
  });

  if (duplicateState === "NO_DUPLICATE") {
    return null;
  }
  const isStrongDuplicateSignal =
    candidates.length > 0 &&
    ((insight.level ?? "none") === "strong" || duplicateState !== "NO_DUPLICATE");
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (forceExpand && isStrongDuplicateSignal) {
      setExpanded(true);
    }
  }, [forceExpand, isStrongDuplicateSignal]);

  const summaryText = useMemo(() => {
    if (isStrongDuplicateSignal) {
      return `${candidates.length} similar rule${candidates.length > 1 ? "s" : ""} found`;
    }
    if (duplicateState === "EXACT_DUPLICATE") {
      return "Exact duplicate detected. This can create unnecessary redundancy.";
    }
    return "Similar rule detected. Review differences before continuing.";
  }, [candidates.length, duplicateState, isStrongDuplicateSignal]);

  const titleText = duplicateState === "EXACT_DUPLICATE" ? "Exact duplicate detected" : "Similar rule detected";
  const reasonText = formatDuplicateReason(insight.reason ?? insight.rationale);
  const cardClass =
    duplicateState === "EXACT_DUPLICATE"
      ? "border-red-300 bg-red-50 p-3"
      : isStrongDuplicateSignal
        ? "border-amber-300 bg-amber-50 p-3"
        : "border-amber-200 bg-amber-50/60 p-3";
  const titleClass = duplicateState === "EXACT_DUPLICATE" ? "text-red-800" : "text-amber-800";
  const summaryClass = duplicateState === "EXACT_DUPLICATE" ? "text-red-700" : "text-amber-700";

  return (
    <Card className={cardClass}>
      <div className="flex items-start gap-2">
        <AlertTriangle
          className={duplicateState === "EXACT_DUPLICATE" ? "mt-0.5 h-4 w-4 text-red-700" : "mt-0.5 h-4 w-4 text-amber-700"}
        />
        <div className="space-y-1">
          <p className={`text-sm font-semibold ${titleClass}`}>{titleText}</p>
          <p className={`text-xs ${summaryClass}`}>{summaryText}</p>
          {reasonText && <p className={`text-xs ${summaryClass}`}>{reasonText}</p>}
        </div>
      </div>

      {isStrongDuplicateSignal && candidates.length > 0 && (
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={() => setExpanded((current) => !current)}
              size="sm"
              type="button"
              variant="outline"
            >
              {expanded ? "Hide similar rules" : "View similar rules"}
            </Button>
            <Button onClick={onContinueToDraft} size="sm" type="button">
              Continue to Draft
            </Button>
          </div>

          {expanded && (
            <DuplicateList
              candidates={candidates}
              onCompareRule={onCompareRule}
              onViewRule={onViewRule}
            />
          )}
        </div>
      )}

      {!isStrongDuplicateSignal && (
        <div className="mt-3">
          <Button onClick={onContinueToDraft} size="sm" type="button">
            Continue to Draft
          </Button>
        </div>
      )}
    </Card>
  );
}
