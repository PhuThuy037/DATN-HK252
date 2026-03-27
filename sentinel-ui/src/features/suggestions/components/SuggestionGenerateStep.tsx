import { useMemo } from "react";
import type { SuggestionDuplicateCandidate } from "@/features/suggestions/types";
import { AppButton } from "@/shared/ui/app-button";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { Card } from "@/shared/ui/card";
import { SuggestionDuplicateAlert } from "@/features/suggestions/components/SuggestionDuplicateAlert";
import { resolveDuplicateUiState } from "@/features/suggestions/components/duplicateUiState";

type SuggestionGenerateStepProps = {
  prompt: string;
  duplicateInsight?: {
    level?: "none" | "weak" | "strong";
    reason?: string;
    duplicateRisk?: string;
    conflictRisk?: string;
    runtimeUsable?: boolean;
    rationale?: string;
    similarRules?: SuggestionDuplicateCandidate[];
    candidates?: SuggestionDuplicateCandidate[];
  } | null;
  onContinueToDraft: () => void;
  onViewDuplicateRule?: (candidate: SuggestionDuplicateCandidate) => void;
  onCompareDuplicateRule?: (candidate: SuggestionDuplicateCandidate) => void;
};

const promptStopWords = new Set([
  "the",
  "and",
  "for",
  "with",
  "that",
  "this",
  "from",
  "your",
  "into",
  "when",
  "then",
  "rule",
  "mask",
  "block",
  "allow",
]);

function extractPromptKeywords(prompt: string) {
  return Array.from(
    new Set(
      prompt
        .split(/[^a-zA-Z0-9_@.-]+/)
        .map((part) => part.trim())
        .filter((part) => part.length >= 3)
        .filter((part) => !promptStopWords.has(part.toLowerCase()))
    )
  ).slice(0, 8);
}

export function SuggestionGenerateStep({
  prompt,
  duplicateInsight,
  onContinueToDraft,
  onViewDuplicateRule,
  onCompareDuplicateRule,
}: SuggestionGenerateStepProps) {
  const similarRules = duplicateInsight?.similarRules ?? duplicateInsight?.candidates ?? [];
  const duplicateState = resolveDuplicateUiState({
    decision: duplicateInsight?.duplicateRisk,
    level: duplicateInsight?.level,
    candidatesCount: similarRules.length,
    topSimilarity: similarRules[0]?.similarity,
  });
  const shouldShowDuplicateBox = duplicateState !== "NO_DUPLICATE";
  const highlightTerms = useMemo(() => extractPromptKeywords(prompt), [prompt]);

  return (
    <AppSectionCard
      description="Review the original request and check for overlapping rules before editing the draft."
      title="Step 1: Generate"
    >
      <Card className="space-y-3 p-4">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Original prompt
          </p>
          <p className="text-sm leading-6 text-foreground">{prompt}</p>
        </div>
      </Card>

      {!shouldShowDuplicateBox ? (
        <div className="flex flex-wrap gap-2">
          <AppButton onClick={onContinueToDraft} type="button">
            Continue to Draft
          </AppButton>
        </div>
      ) : (
        <SuggestionDuplicateAlert
          forceExpand={duplicateState === "EXACT_DUPLICATE"}
          highlightTerms={highlightTerms}
          insight={duplicateInsight}
          onCompareRule={onCompareDuplicateRule}
          onContinueToDraft={onContinueToDraft}
          onViewRule={onViewDuplicateRule}
        />
      )}
    </AppSectionCard>
  );
}
