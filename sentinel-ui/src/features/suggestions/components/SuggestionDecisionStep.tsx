import type { SuggestionStatus } from "@/features/suggestions/types";
import { canConfirm, canReject } from "@/features/suggestions/components/StatusBadge";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppButton } from "@/shared/ui/app-button";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { StatusBadge } from "@/shared/ui/status-badge";

type SuggestionDecisionStepProps = {
  status: SuggestionStatus;
  isConfirming: boolean;
  isRejecting: boolean;
  duplicateRisk?: string | null;
  runtimeUsable?: boolean;
  runtimeWarnings?: string[];
  onBack: () => void;
  onOpenConfirm: () => void;
  onOpenReject: () => void;
};

function duplicateRiskTone(value?: string | null) {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (normalized.includes("exact") || normalized.includes("high")) {
    return "danger" as const;
  }
  if (normalized.includes("near") || normalized.includes("similar") || normalized.includes("medium")) {
    return "warning" as const;
  }
  if (normalized.includes("none") || normalized.includes("low") || normalized.includes("different")) {
    return "success" as const;
  }
  return "muted" as const;
}

export function SuggestionDecisionStep({
  status,
  isConfirming,
  isRejecting,
  duplicateRisk,
  runtimeUsable = true,
  runtimeWarnings = [],
  onBack,
  onOpenConfirm,
  onOpenReject,
}: SuggestionDecisionStepProps) {
  const isExactDuplicate = String(duplicateRisk ?? "").trim().toLowerCase().includes("exact");
  const hasDuplicateWarning =
    typeof duplicateRisk === "string" &&
    !["", "none", "different", "low"].includes(duplicateRisk.trim().toLowerCase());

  return (
    <AppSectionCard
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge label="Step 5 of 6" tone="muted" />
          {duplicateRisk ? <StatusBadge label={duplicateRisk} tone={duplicateRiskTone(duplicateRisk)} /> : null}
        </div>
      }
      description="Confirming locks the draft and moves it to approved. Rejecting closes the review workflow."
      title="Confirm"
    >

      <div className="rounded-xl border border-border/80 bg-background p-4">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge label={`Status: ${status}`} tone="muted" />
          {duplicateRisk ? <StatusBadge label={`Duplicate risk: ${duplicateRisk}`} tone={duplicateRiskTone(duplicateRisk)} /> : null}
        </div>
        <p className="mt-3 text-sm text-muted-foreground">
          Use confirm when the draft is ready for approval. Go back if you still need to revise the draft or compare duplicates.
        </p>
      </div>

      {hasDuplicateWarning ? (
        <AppAlert
          description={
            isExactDuplicate
              ? "An exact duplicate was detected. Review the existing rule and adjust the draft before confirming."
              : "This suggestion still carries a duplicate signal. Review the compare and generate steps before confirming."
          }
          title={isExactDuplicate ? "Confirmation blocked" : "Duplicate warning"}
          variant={isExactDuplicate ? "error" : "warning"}
        />
      ) : null}

      {!runtimeUsable || runtimeWarnings.length > 0 ? (
        <AppAlert
          description={
            <div className="space-y-1">
              <p>May not work as expected at runtime, but you can still confirm and apply this suggestion.</p>
              {runtimeWarnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          }
          title="Runtime usability: warning"
          variant="warning"
        />
      ) : null}

      <div className="flex flex-wrap gap-2">
        <AppButton onClick={onBack} type="button" variant="secondary">
          Back
        </AppButton>
        <AppButton
          disabled={!canConfirm(status) || isConfirming || isExactDuplicate}
          onClick={onOpenConfirm}
          type="button"
        >
          {isConfirming ? "Confirming..." : "Confirm suggestion"}
        </AppButton>

        <AppButton
          disabled={!canReject(status) || isRejecting}
          onClick={onOpenReject}
          type="button"
          variant="danger"
        >
          {isRejecting ? "Rejecting..." : "Reject suggestion"}
        </AppButton>
      </div>
    </AppSectionCard>
  );
}
