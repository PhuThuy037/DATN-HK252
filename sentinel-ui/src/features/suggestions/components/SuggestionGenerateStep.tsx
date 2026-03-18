import { useState } from "react";
import type { SuggestionDuplicateCandidate } from "@/features/suggestions/types";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { SuggestionDuplicateAlert } from "@/features/suggestions/components/SuggestionDuplicateAlert";

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
  const duplicateCount = similarRules.length;
  const canViewSimilarRules =
    (duplicateInsight?.level ?? "none") === "strong" && duplicateCount > 0;
  const [forceExpandDuplicates, setForceExpandDuplicates] = useState(false);

  return (
    <Card className="space-y-4 p-4">
      <h2 className="text-base font-semibold">Generate</h2>
      <p className="text-sm text-muted-foreground">
        Review duplicate signal first, then continue to draft when you are ready.
      </p>

      <div className="rounded-md border bg-muted/30 p-3">
        <p className="text-xs font-medium text-muted-foreground">Original prompt</p>
        <p className="mt-1 text-sm">{prompt}</p>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button onClick={onContinueToDraft} type="button">
          Continue to Draft
        </Button>
        <Button
          disabled={!canViewSimilarRules}
          onClick={() => setForceExpandDuplicates(true)}
          type="button"
          variant="outline"
        >
          View similar rules
        </Button>
      </div>

      <SuggestionDuplicateAlert
        forceExpand={forceExpandDuplicates}
        insight={duplicateInsight}
        onCompareRule={onCompareDuplicateRule}
        onViewRule={onViewDuplicateRule}
      />
    </Card>
  );
}
