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
  onConfirm: () => Promise<void> | void;
  onReject: (reason?: string | null) => Promise<void> | void;
  onApply: () => Promise<void> | void;
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
  onConfirm,
  onReject,
  onApply,
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
        <Button disabled={isConfirming} onClick={() => void onConfirm()} type="button" variant="outline">
          {isConfirming ? "Confirming..." : "Confirm"}
        </Button>
      )}

      {canReject(status) && (
        <Button
          disabled={isRejecting}
          onClick={() => {
            const reason = window.prompt("Reject reason (optional)", "") ?? "";
            void onReject(reason.trim() || null);
          }}
          type="button"
          variant="outline"
        >
          {isRejecting ? "Rejecting..." : "Reject"}
        </Button>
      )}

      {canApply(status) && (
        <Button
          disabled={isApplying}
          onClick={() => {
            const confirmed = window.confirm("Apply this approved suggestion?");
            if (confirmed) {
              void onApply();
            }
          }}
          type="button"
        >
          {isApplying ? "Applying..." : "Apply"}
        </Button>
      )}

      {isReadOnly && <p className="text-xs text-muted-foreground">Read-only status: {status}</p>}
    </div>
  );
}
