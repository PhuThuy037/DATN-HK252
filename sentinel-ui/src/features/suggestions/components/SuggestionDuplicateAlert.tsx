import { useEffect, useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import type { SuggestionDuplicateCandidate } from "@/features/suggestions/types";
import { AppButton } from "@/shared/ui/app-button";
import { Card } from "@/shared/ui/card";
import { DuplicateList } from "@/features/suggestions/components/DuplicateList";
import { resolveDuplicateUiState } from "@/features/suggestions/components/duplicateUiState";
import { StatusBadge } from "@/shared/ui/status-badge";

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
  highlightTerms?: string[];
  onViewRule?: (candidate: SuggestionDuplicateCandidate) => void;
  onCompareRule?: (candidate: SuggestionDuplicateCandidate) => void;
  onContinueToDraft: () => void;
  forceExpand?: boolean;
};

type DuplicatePresentation = {
  title: string;
  summary: string;
  tone: "danger" | "warning";
  cardClassName: string;
  iconClassName: string;
};

function formatDuplicateReason(reason?: string | null) {
  const text = String(reason ?? "").trim();
  if (!text) {
    return null;
  }

  const normalized = text.toLowerCase();
  if (normalized.includes("semantic_signature_match")) {
    return "Detected through semantic matching against an existing rule.";
  }

  if (/^[a-z0-9_]+$/.test(normalized) || normalized.includes("_")) {
    return null;
  }

  return text;
}

function getTopSimilarity(candidates: SuggestionDuplicateCandidate[]) {
  const value = candidates[0]?.similarity;
  return typeof value === "number" && !Number.isNaN(value) ? value : null;
}

function getDuplicatePresentation(
  duplicateState: ReturnType<typeof resolveDuplicateUiState>,
  candidates: SuggestionDuplicateCandidate[]
): DuplicatePresentation {
  const topSimilarity = getTopSimilarity(candidates);
  const topPercent =
    typeof topSimilarity === "number" ? `${Math.round(topSimilarity * 100)}%` : "high";

  if (duplicateState === "EXACT_DUPLICATE") {
    return {
      title: "Exact duplicate detected",
      summary: "This suggestion appears to match an existing rule and is likely redundant.",
      tone: "danger",
      cardClassName: "border-danger-border bg-danger-muted",
      iconClassName: "text-danger",
    };
  }

  if (typeof topSimilarity === "number" && topSimilarity > 0.9) {
    return {
      title: "Very similar rule detected",
      summary: `A highly overlapping rule already exists (${topPercent} similarity). Review differences carefully before continuing.`,
      tone: "danger",
      cardClassName: "border-danger-border bg-danger-muted/70",
      iconClassName: "text-danger",
    };
  }

  return {
    title: "Similar rule detected",
    summary: `A related rule already exists (${topPercent} similarity). Review it before continuing to draft.`,
    tone: "warning",
    cardClassName: "border-warning-border bg-warning-muted",
    iconClassName: "text-warning",
  };
}

export function SuggestionDuplicateAlert({
  insight,
  highlightTerms = [],
  onViewRule,
  onCompareRule,
  onContinueToDraft,
  forceExpand = false,
}: SuggestionDuplicateAlertProps) {
  const candidates = insight?.similarRules ?? insight?.candidates ?? [];
  const duplicateState = resolveDuplicateUiState({
    decision: insight?.duplicateRisk,
    level: insight?.level,
    candidatesCount: candidates.length,
    topSimilarity: candidates[0]?.similarity,
  });

  const hasCandidates = candidates.length > 0;
  const [expanded, setExpanded] = useState(forceExpand || duplicateState === "EXACT_DUPLICATE");

  useEffect(() => {
    if (forceExpand && hasCandidates) {
      setExpanded(true);
    }
  }, [forceExpand, hasCandidates]);

  const reasonText = formatDuplicateReason(insight?.reason ?? insight?.rationale);
  const presentation = useMemo(
    () => getDuplicatePresentation(duplicateState, candidates),
    [candidates, duplicateState]
  );

  if (!insight || duplicateState === "NO_DUPLICATE") {
    return null;
  }

  return (
    <Card className={`space-y-4 p-4 ${presentation.cardClassName}`}>
      <div className="flex items-start gap-3">
        <AlertTriangle className={`mt-0.5 h-5 w-5 shrink-0 ${presentation.iconClassName}`} />
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-foreground">{presentation.title}</p>
            <StatusBadge
              label={
                duplicateState === "EXACT_DUPLICATE"
                  ? "Exact duplicate"
                  : presentation.tone === "danger"
                    ? "Very similar"
                    : "Similar"
              }
              tone={presentation.tone}
            />
          </div>
          <p className="text-sm text-muted-foreground">{presentation.summary}</p>
          {duplicateState === "EXACT_DUPLICATE" ? (
            <p className="text-xs font-medium text-danger">
              Confirmation is blocked until this duplicate is reviewed and the draft is changed.
            </p>
          ) : null}
          {reasonText ? <p className="text-xs text-muted-foreground">{reasonText}</p> : null}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {hasCandidates ? (
          <AppButton
            onClick={() => setExpanded((current) => !current)}
            size="sm"
            type="button"
            variant="secondary"
          >
            {expanded ? "Hide similar rules" : `Show similar rules (${candidates.length})`}
          </AppButton>
        ) : null}
        <AppButton onClick={onContinueToDraft} size="sm" type="button">
          Continue to Draft
        </AppButton>
      </div>

      {expanded && hasCandidates ? (
        <DuplicateList
          candidates={candidates}
          highlightTerms={highlightTerms}
          onCompareRule={onCompareRule}
          onViewRule={onViewRule}
        />
      ) : null}
    </Card>
  );
}
