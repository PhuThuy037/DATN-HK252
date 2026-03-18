import { Button } from "@/shared/ui/button";
import {
  canApply,
  canConfirm,
  canReject,
  canSimulate,
} from "@/features/suggestions/components/StatusBadge";
import type { SuggestionStatus } from "@/features/suggestions/types";

type SuggestionActionsProps = {
  status: SuggestionStatus;
  hasDirtyDraft: boolean;
  isSaving?: boolean;
  isConfirming?: boolean;
  isRejecting?: boolean;
  isApplying?: boolean;
  onSaveDraft: () => Promise<void> | void;
  onOpenSimulate: () => void;
  onOpenConfirm: () => void;
  onOpenReject: () => void;
  onOpenApply: () => void;
};

export function SuggestionActions({
  status,
  hasDirtyDraft,
  isSaving = false,
  isConfirming = false,
  isRejecting = false,
  isApplying = false,
  onSaveDraft,
  onOpenSimulate,
  onOpenConfirm,
  onOpenReject,
  onOpenApply,
}: SuggestionActionsProps) {
  const isReadOnly = !canSimulate(status) && !canReject(status) && !canApply(status);

  return (
    <div className="flex flex-wrap items-center gap-2">
      {status === "draft" && (
        <Button disabled={!hasDirtyDraft || isSaving} onClick={() => void onSaveDraft()} type="button">
          {isSaving ? "Saving..." : "Save Draft"}
        </Button>
      )}

      {canSimulate(status) && (
        <Button onClick={onOpenSimulate} type="button" variant="outline">
          Simulate
        </Button>
      )}

      {canConfirm(status) && (
        <Button disabled={isConfirming} onClick={onOpenConfirm} type="button" variant="outline">
          {isConfirming ? "Confirming..." : "Confirm"}
        </Button>
      )}

      {canReject(status) && (
        <Button disabled={isRejecting} onClick={onOpenReject} type="button" variant="outline">
          {isRejecting ? "Rejecting..." : "Reject"}
        </Button>
      )}

      {canApply(status) && (
        <Button disabled={isApplying} onClick={onOpenApply} type="button">
          {isApplying ? "Applying..." : "Apply"}
        </Button>
      )}

      {isReadOnly && <p className="text-xs text-muted-foreground">Read-only status: {status}</p>}
    </div>
  );
}
