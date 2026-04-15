import type { RuleSuggestionSimulateOut, SuggestionStatus } from "@/features/suggestions/types";
import { canSimulate } from "@/features/suggestions/components/StatusBadge";
import { SimulatePanel } from "@/features/suggestions/components/SimulatePanel";
import { AppButton } from "@/shared/ui/app-button";
import { appActionRowClassName } from "@/shared/ui/design-tokens";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { StatusBadge } from "@/shared/ui/status-badge";

type SuggestionSimulateStepProps = {
  status: SuggestionStatus;
  isSubmitting: boolean;
  errorMessage?: string | null;
  result?: RuleSuggestionSimulateOut | null;
  highlightTerms?: string[];
  showSemanticNote?: boolean;
  onSimulate: (payload: { samples: string[]; include_examples: boolean }) => Promise<void> | void;
  onBack: () => void;
  onContinue: () => void;
};

export function SuggestionSimulateStep({
  status,
  isSubmitting,
  errorMessage,
  result,
  highlightTerms,
  showSemanticNote = false,
  onSimulate,
  onBack,
  onContinue,
}: SuggestionSimulateStepProps) {
  return (
    <AppSectionCard
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge label="Step 3 of 6" tone="muted" />
        </div>
      }
      description="Run sample inputs to see actual runtime behavior before moving to review."
      title="Simulate"
    >
      <SimulatePanel
        disabled={!canSimulate(status)}
        errorMessage={errorMessage}
        highlightTerms={highlightTerms}
        isSubmitting={isSubmitting}
        onSimulate={onSimulate}
        result={result}
      />

      {showSemanticNote ? (
        <AppAlert
          description="Simulation is most reliable for exact and pattern-based rules. Validate advanced semantic behavior in chat/runtime."
          title="Simulation note"
          variant="warning"
        />
      ) : null}

      <div className={appActionRowClassName}>
        <AppButton onClick={onBack} type="button" variant="secondary">
          Back
        </AppButton>
        <AppButton disabled={isSubmitting} onClick={onContinue} type="button">
          Continue to Review
        </AppButton>
      </div>
    </AppSectionCard>
  );
}
