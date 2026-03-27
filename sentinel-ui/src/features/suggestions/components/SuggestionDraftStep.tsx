import type { SuggestionDraft, SuggestionStatus } from "@/features/suggestions/types";
import { canEditDraft } from "@/features/suggestions/components/StatusBadge";
import { DraftEditor } from "@/features/suggestions/components/DraftEditor";
import { AppButton } from "@/shared/ui/app-button";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { StatusBadge } from "@/shared/ui/status-badge";

type SuggestionDraftStepProps = {
  status: SuggestionStatus;
  draft: SuggestionDraft;
  hasDirtyDraft: boolean;
  isSaving: boolean;
  saveState?: "saved" | "dirty" | "saving" | "error";
  validationError?: string | null;
  onDraftChange: (nextDraft: SuggestionDraft) => void;
  onSaveDraft: () => void;
  onBack: () => void;
  onContinue: () => void;
};

export function SuggestionDraftStep({
  status,
  draft,
  hasDirtyDraft,
  isSaving,
  saveState = "saved",
  validationError,
  onDraftChange,
  onSaveDraft,
  onBack,
  onContinue,
}: SuggestionDraftStepProps) {
  const editable = canEditDraft(status);
  const saveLabel =
    saveState === "saving"
      ? "Autosaving"
      : saveState === "dirty"
        ? "Unsaved"
        : saveState === "error"
          ? "Needs attention"
          : "Saved";
  const saveTone =
    saveState === "saving"
      ? "primary"
      : saveState === "dirty"
        ? "warning"
        : saveState === "error"
          ? "danger"
          : "success";

  return (
    <AppSectionCard
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge label="Step 2 of 6" tone="muted" />
          <StatusBadge label={saveLabel} tone={saveTone} />
        </div>
      }
      description="Edit rule details, confirm the behavior, and let autosave keep the draft current while you work."
      title="Draft"
    >

      <DraftEditor
        draft={draft}
        onDraftChange={onDraftChange}
        readOnly={!editable}
        validationError={validationError}
      />

      <div className="flex items-center justify-between gap-2 border-t pt-3">
        <p className="text-xs text-muted-foreground">
          {hasDirtyDraft
            ? "Changes are waiting to be saved."
            : "Draft is up to date and ready for simulation."}
        </p>
        <div className="flex flex-wrap gap-2">
          <AppButton onClick={onBack} type="button" variant="secondary">
            Back
          </AppButton>
          <AppButton
            disabled={!editable || !hasDirtyDraft || isSaving}
            onClick={onSaveDraft}
            type="button"
            variant="secondary"
          >
            {isSaving ? "Saving..." : "Save now"}
          </AppButton>
          <AppButton disabled={hasDirtyDraft || saveState === "saving"} onClick={onContinue} type="button">
            Continue to Simulate
          </AppButton>
        </div>
      </div>
    </AppSectionCard>
  );
}
