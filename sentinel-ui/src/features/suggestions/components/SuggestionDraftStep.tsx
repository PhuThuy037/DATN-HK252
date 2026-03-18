import type { SuggestionDraft, SuggestionStatus } from "@/features/suggestions/types";
import { canEditDraft } from "@/features/suggestions/components/StatusBadge";
import { DraftEditor } from "@/features/suggestions/components/DraftEditor";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";

type SuggestionDraftStepProps = {
  status: SuggestionStatus;
  draft: SuggestionDraft;
  hasDirtyDraft: boolean;
  isSaving: boolean;
  validationError?: string | null;
  onDraftChange: (nextDraft: SuggestionDraft) => void;
  onSaveDraft: () => void;
};

export function SuggestionDraftStep({
  status,
  draft,
  hasDirtyDraft,
  isSaving,
  validationError,
  onDraftChange,
  onSaveDraft,
}: SuggestionDraftStepProps) {
  const editable = canEditDraft(status);

  return (
    <Card className="space-y-3 p-4">
      <div>
        <h2 className="text-base font-semibold">Draft</h2>
        <p className="text-sm text-muted-foreground">
          Edit rule fields and context terms before moving to decision.
        </p>
      </div>

      <DraftEditor
        draft={draft}
        onDraftChange={onDraftChange}
        readOnly={!editable}
        validationError={validationError}
      />

      <div className="flex items-center justify-between gap-2 border-t pt-3">
        <p className="text-xs text-muted-foreground">
          {hasDirtyDraft ? "You have unsaved changes." : "Draft is saved."}
        </p>
        <Button
          disabled={!editable || !hasDirtyDraft || isSaving}
          onClick={onSaveDraft}
          type="button"
        >
          {isSaving ? "Saving..." : "Save Draft"}
        </Button>
      </div>
    </Card>
  );
}
