import type { RuleSuggestionSimulateOut, SuggestionStatus } from "@/features/suggestions/types";
import { canSimulate } from "@/features/suggestions/components/StatusBadge";
import { SimulatePanel } from "@/features/suggestions/components/SimulatePanel";
import { AppButton } from "@/shared/ui/app-button";
import { appActionRowClassName } from "@/shared/ui/design-tokens";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { StatusBadge } from "@/shared/ui/status-badge";

type SuggestionSimulateStepProps = {
  status: SuggestionStatus;
  isSubmitting: boolean;
  errorMessage?: string | null;
  result?: RuleSuggestionSimulateOut | null;
  expectedAction?: string | null;
  highlightTerms?: string[];
  onSimulate: (payload: { samples: string[]; include_examples: boolean }) => Promise<void> | void;
  onBack: () => void;
  onContinue: () => void;
};

export function SuggestionSimulateStep({
  status,
  isSubmitting,
  errorMessage,
  result,
  expectedAction,
  highlightTerms,
  onSimulate,
  onBack,
  onContinue,
}: SuggestionSimulateStepProps) {
  return (
    <AppSectionCard
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge label="Step 3 of 6" tone="muted" />
          {expectedAction ? <StatusBadge label={`Expected ${expectedAction}`} tone="primary" /> : null}
        </div>
      }
      description="Run sample inputs to verify how the draft behaves before moving to review."
      title="Simulate"
    >

      <SimulatePanel
        disabled={!canSimulate(status)}
        errorMessage={errorMessage}
        expectedAction={expectedAction}
        highlightTerms={highlightTerms}
        isSubmitting={isSubmitting}
        onSimulate={onSimulate}
        result={result}
      />

      <div className={appActionRowClassName}>
        <AppButton onClick={onBack} type="button" variant="secondary">
          Back
        </AppButton>
        <AppButton disabled={!result} onClick={onContinue} type="button">
          Continue to Review
        </AppButton>
      </div>
    </AppSectionCard>
  );
}
