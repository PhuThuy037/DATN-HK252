import type { RuleSuggestionGetOut } from "@/features/suggestions/types";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppButton } from "@/shared/ui/app-button";
import { Card } from "@/shared/ui/card";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { StatusBadge } from "@/shared/ui/status-badge";

function formatConfidence(value: unknown) {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) {
    return "-";
  }

  const percent = numeric <= 1 ? numeric * 100 : numeric;
  return `${Math.round(percent)}%`;
}

function duplicateRiskTone(value: string | undefined) {
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

type SuggestionReviewStepProps = {
  suggestion: RuleSuggestionGetOut;
  onBack: () => void;
  onContinue: () => void;
};

export function SuggestionReviewStep({
  suggestion,
  onBack,
  onContinue,
}: SuggestionReviewStepProps) {
  const duplicateRisk = String(suggestion.quality_signals?.duplicate_risk ?? "-");
  const runtimeUsable = Boolean(suggestion.quality_signals?.runtime_usable);
  const intentConfidence = formatConfidence(suggestion.quality_signals?.intent_confidence);
  const readyToApply = runtimeUsable && !String(duplicateRisk).toLowerCase().includes("exact");

  return (
    <AppSectionCard
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge label="Step 4 of 6" tone="muted" />
          <StatusBadge
            label={readyToApply ? "Ready to confirm" : "Review carefully"}
            tone={readyToApply ? "success" : "warning"}
          />
        </div>
      }
      description="Review the quality signals and make sure the draft is ready for confirmation."
      title="Review"
    >

      <Card className="space-y-4 border-border/80 p-4">
        <div className="space-y-1">
          <p className="text-sm font-semibold text-foreground">Summary</p>
          <p className="text-sm text-muted-foreground">
            Review the most important quality signals before confirming or rejecting this suggestion.
          </p>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          <div
            className={`rounded-xl border px-4 py-3 ${
              readyToApply
                ? "border-success-border bg-success-muted"
                : "border-warning-border bg-warning-muted"
            }`}
          >
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Ready to apply
            </p>
            <div className="mt-2">
              <StatusBadge
                label={readyToApply ? "Ready" : "Needs review"}
                tone={readyToApply ? "success" : "warning"}
              />
            </div>
          </div>

          <div className="rounded-xl border border-primary/20 bg-primary/5 px-4 py-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Intent confidence
            </p>
            <p className="mt-1 text-2xl font-semibold text-foreground">{intentConfidence}</p>
          </div>

          <div className="rounded-xl border border-border/80 bg-background px-4 py-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Duplicate risk
            </p>
            <div className="mt-2">
              <StatusBadge label={duplicateRisk} tone={duplicateRiskTone(duplicateRisk)} />
            </div>
          </div>

          <div className={`rounded-xl border px-4 py-3 ${runtimeUsable ? "border-success-border bg-success-muted" : "border-warning-border bg-warning-muted"}`}>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Runtime usable
            </p>
            <div className="mt-2">
              <StatusBadge status={runtimeUsable ? "approved" : "rejected"} />
            </div>
          </div>
        </div>
      </Card>

      <div className="rounded-xl border border-border/80 bg-background p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Explanation summary
        </p>
        <p className="mt-2 text-sm text-foreground">{suggestion.explanation?.summary ?? "-"}</p>
        <div className="mt-3 grid gap-2 text-sm text-muted-foreground md:grid-cols-2">
          <p>Detected intent: {suggestion.explanation?.detected_intent ?? "-"}</p>
          <p>Action reason: {suggestion.explanation?.action_reason ?? "-"}</p>
        </div>
      </div>

      {suggestion.quality_signals?.runtime_warnings?.length ? (
        <AppAlert
          description={
            <div className="space-y-1">
              {suggestion.quality_signals.runtime_warnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          }
          title="Runtime warnings"
          variant="warning"
        />
      ) : null}

      <div className="flex flex-wrap justify-end gap-2 border-t pt-3">
        <AppButton onClick={onBack} type="button" variant="secondary">
          Back
        </AppButton>
        <AppButton disabled={!runtimeUsable} onClick={onContinue} type="button">
          Continue to Confirm
        </AppButton>
      </div>
    </AppSectionCard>
  );
}
