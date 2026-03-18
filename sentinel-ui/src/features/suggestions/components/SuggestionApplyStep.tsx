import type { RuleSuggestionGetOut } from "@/features/suggestions/types";
import { canApply } from "@/features/suggestions/components/StatusBadge";
import { SuggestionApplyResultCard } from "@/features/suggestions/components/SuggestionApplyResultCard";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";

type SuggestionApplyStepProps = {
  suggestion: RuleSuggestionGetOut;
  isApplying: boolean;
  onOpenApply: () => void;
};

export function SuggestionApplyStep({ suggestion, isApplying, onOpenApply }: SuggestionApplyStepProps) {
  return (
    <Card className="space-y-3 p-4">
      <h2 className="text-base font-semibold">Apply</h2>

      {suggestion.status === "applied" ? (
        <>
          <p className="text-sm text-muted-foreground">Suggestion has been applied successfully.</p>
          {suggestion.applied_result_json ? (
            <SuggestionApplyResultCard appliedResultJson={suggestion.applied_result_json} />
          ) : (
            <p className="text-sm text-muted-foreground">No apply result payload found.</p>
          )}
        </>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            Apply this approved suggestion to create/update runtime rule data.
          </p>
          <div>
            <Button
              disabled={!canApply(suggestion.status) || isApplying}
              onClick={onOpenApply}
              type="button"
            >
              {isApplying ? "Applying..." : "Apply suggestion"}
            </Button>
          </div>
        </>
      )}
    </Card>
  );
}
