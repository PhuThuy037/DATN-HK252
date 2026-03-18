import type { SuggestionStatus } from "@/features/suggestions/types";
import { canConfirm, canReject } from "@/features/suggestions/components/StatusBadge";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";

type SuggestionDecisionStepProps = {
  status: SuggestionStatus;
  isConfirming: boolean;
  isRejecting: boolean;
  onOpenConfirm: () => void;
  onOpenReject: () => void;
};

export function SuggestionDecisionStep({
  status,
  isConfirming,
  isRejecting,
  onOpenConfirm,
  onOpenReject,
}: SuggestionDecisionStepProps) {
  return (
    <Card className="space-y-3 p-4">
      <h2 className="text-base font-semibold">Decision</h2>
      <p className="text-sm text-muted-foreground">
        Confirm will lock draft editing and move status to approved. Reject will close this suggestion.
      </p>

      <div className="flex flex-wrap gap-2">
        <Button
          disabled={!canConfirm(status) || isConfirming}
          onClick={onOpenConfirm}
          type="button"
        >
          {isConfirming ? "Confirming..." : "Confirm suggestion"}
        </Button>

        <Button
          disabled={!canReject(status) || isRejecting}
          onClick={onOpenReject}
          type="button"
          variant="outline"
        >
          {isRejecting ? "Rejecting..." : "Reject suggestion"}
        </Button>
      </div>
    </Card>
  );
}
