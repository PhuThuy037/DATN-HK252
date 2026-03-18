import type { RuleSuggestionSimulateOut, SuggestionStatus } from "@/features/suggestions/types";
import { canSimulate } from "@/features/suggestions/components/StatusBadge";
import { SimulatePanel } from "@/features/suggestions/components/SimulatePanel";
import { Card } from "@/shared/ui/card";

type SuggestionSimulateStepProps = {
  status: SuggestionStatus;
  isSubmitting: boolean;
  errorMessage?: string | null;
  result?: RuleSuggestionSimulateOut | null;
  onSimulate: (payload: { samples: string[]; include_examples: boolean }) => Promise<void> | void;
};

export function SuggestionSimulateStep({
  status,
  isSubmitting,
  errorMessage,
  result,
  onSimulate,
}: SuggestionSimulateStepProps) {
  return (
    <Card className="space-y-3 p-4">
      <h2 className="text-base font-semibold">Simulate</h2>
      <p className="text-sm text-muted-foreground">
        Run test samples to validate behavior before confirmation.
      </p>

      <SimulatePanel
        disabled={!canSimulate(status)}
        errorMessage={errorMessage}
        isSubmitting={isSubmitting}
        onSimulate={onSimulate}
        result={result}
      />
    </Card>
  );
}
