import type { SuggestionDuplicateCandidate } from "@/features/suggestions/types";
import { Button } from "@/shared/ui/button";
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

  return (
    <Card className="space-y-4 p-4">
      <h2 className="text-base font-semibold">Generate</h2>
      <p className="text-sm text-muted-foreground">Review duplicate signal before continuing.</p>

      <div className="rounded-md border bg-muted/30 p-3">
        <p className="text-xs font-medium text-muted-foreground">Original prompt</p>
        <p className="mt-1 text-sm">{prompt}</p>
      </div>

      {!shouldShowDuplicateBox && (
        <div className="flex flex-wrap gap-2">
          <Button onClick={onContinueToDraft} type="button">
            Continue to Draft
          </Button>
        </div>
      )}

      {shouldShowDuplicateBox && (
        <SuggestionDuplicateAlert
          insight={duplicateInsight}
          onCompareRule={onCompareDuplicateRule}
          onContinueToDraft={onContinueToDraft}
          onViewRule={onViewDuplicateRule}
        />
      )}
    </Card>
  );
}
