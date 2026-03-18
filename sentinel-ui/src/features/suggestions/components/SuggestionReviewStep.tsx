import type { RuleSuggestionGetOut } from "@/features/suggestions/types";
import { Card } from "@/shared/ui/card";

function qualitySignalsToRows(signals: RuleSuggestionGetOut["quality_signals"] | undefined) {
  if (!signals) {
    return [] as Array<{ label: string; value: string }>;
  }

  return [
    { label: "Intent confidence", value: String(signals.intent_confidence ?? "-") },
    { label: "Duplicate risk", value: String(signals.duplicate_risk ?? "-") },
    { label: "Conflict risk", value: String(signals.conflict_risk ?? "-") },
    { label: "Runtime usable", value: signals.runtime_usable ? "Yes" : "No" },
    { label: "Generation source", value: String(signals.generation_source ?? "-") },
  ];
}

type SuggestionReviewStepProps = {
  suggestion: RuleSuggestionGetOut;
};

export function SuggestionReviewStep({ suggestion }: SuggestionReviewStepProps) {
  const rows = qualitySignalsToRows(suggestion.quality_signals);

  return (
    <Card className="space-y-4 p-4">
      <h2 className="text-base font-semibold">Review</h2>
      <p className="text-sm text-muted-foreground">
        Final review before decision.
      </p>

      <div className="rounded-md border p-3">
        <p className="text-xs font-medium text-muted-foreground">Explanation summary</p>
        <p className="mt-1 text-sm">{suggestion.explanation?.summary ?? "-"}</p>
        <p className="mt-2 text-xs text-muted-foreground">
          Detected intent: {suggestion.explanation?.detected_intent ?? "-"}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          Action reason: {suggestion.explanation?.action_reason ?? "-"}
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {rows.map((row) => (
          <div className="rounded-md border p-3" key={row.label}>
            <p className="text-xs text-muted-foreground">{row.label}</p>
            <p className="text-sm font-medium">{row.value}</p>
          </div>
        ))}
      </div>

      {suggestion.quality_signals?.runtime_warnings?.length ? (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
          {suggestion.quality_signals.runtime_warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </div>
      ) : null}
    </Card>
  );
}
