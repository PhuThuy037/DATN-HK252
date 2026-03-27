import { useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { HighlightedText } from "@/features/suggestions/components/HighlightedText";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppButton } from "@/shared/ui/app-button";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { FieldHelpText } from "@/shared/ui/field-help-text";
import { InlineErrorText } from "@/shared/ui/inline-error-text";
import { StatusBadge } from "@/shared/ui/status-badge";
import { Textarea } from "@/shared/ui/textarea";
import type { RuleSuggestionSimulateOut } from "@/features/suggestions/types";

type SimulatePanelProps = {
  disabled?: boolean;
  isSubmitting?: boolean;
  errorMessage?: string | null;
  result?: RuleSuggestionSimulateOut | null;
  expectedAction?: string | null;
  highlightTerms?: string[];
  onSimulate: (payload: { samples: string[]; include_examples: boolean }) => Promise<void> | void;
};

function parseSamples(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function toActionTone(action?: string | null): "success" | "warning" | "danger" | "muted" {
  const normalized = String(action ?? "").trim().toUpperCase();
  if (normalized === "ALLOW") {
    return "success";
  }
  if (normalized === "MASK") {
    return "warning";
  }
  if (normalized === "BLOCK") {
    return "danger";
  }
  return "muted";
}

export function SimulatePanel({
  disabled = false,
  isSubmitting = false,
  errorMessage,
  result,
  expectedAction,
  highlightTerms = [],
  onSimulate,
}: SimulatePanelProps) {
  const [samplesInput, setSamplesInput] = useState("");
  const [includeExamples, setIncludeExamples] = useState(true);
  const [validationError, setValidationError] = useState<string | null>(null);

  const sampleCount = useMemo(() => parseSamples(samplesInput).length, [samplesInput]);
  const normalizedExpectedAction = String(expectedAction ?? "").trim().toUpperCase();

  const handleSimulate = async () => {
    const samples = parseSamples(samplesInput);
    if (samples.length === 0) {
      setValidationError("Please enter at least one sample.");
      return;
    }

    setValidationError(null);
    await onSimulate({
      samples,
      include_examples: includeExamples,
    });
  };

  return (
    <div className="space-y-4">
      <AppSectionCard
        actions={
          <StatusBadge label={`${sampleCount} sample${sampleCount === 1 ? "" : "s"}`} tone="muted" />
        }
        description="Add sample inputs to validate how this draft behaves before confirmation."
        title="Simulation input"
      >

        <Textarea
          className="min-h-[150px]"
          disabled={disabled}
          onChange={(event) => setSamplesInput(event.target.value)}
          placeholder="One sample per line"
          value={samplesInput}
        />
        <FieldHelpText>Enter one test sample per line so the results are easy to compare.</FieldHelpText>

        <label className="inline-flex items-center gap-2 text-xs text-muted-foreground">
          <input
            checked={includeExamples}
            disabled={disabled}
            onChange={(event) => setIncludeExamples(event.target.checked)}
            type="checkbox"
          />
          Include example-based samples
        </label>

        {validationError ? <InlineErrorText>{validationError}</InlineErrorText> : null}

        {errorMessage ? (
          <AppAlert
            description={errorMessage}
            icon={<AlertTriangle className="mt-0.5 h-4 w-4 text-danger" />}
            title="Simulation failed"
            variant="error"
          />
        ) : null}

        <div className="flex justify-end">
          <AppButton disabled={disabled || isSubmitting} onClick={() => void handleSimulate()} type="button">
            {isSubmitting ? "Simulating..." : "Simulate"}
          </AppButton>
        </div>
      </AppSectionCard>

      {result ? (
        <AppSectionCard
          description="Review predicted actions first, then scan the detailed sample-by-sample table."
          title="Simulation results"
        >

          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-xl border border-border/80 bg-background px-4 py-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Samples</p>
              <p className="mt-1 text-2xl font-semibold text-foreground">{result.sample_size}</p>
            </div>
            <div className="rounded-xl border border-success-border bg-success-muted px-4 py-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Pass count</p>
              <p className="mt-1 text-2xl font-semibold text-foreground">{result.matched_count}</p>
            </div>
            <div className="rounded-xl border border-border/80 bg-background px-4 py-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Runtime usable</p>
              <div className="mt-2">
                <StatusBadge status={result.runtime_usable ? "approved" : "rejected"} />
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <StatusBadge label={`Allow ${result.action_breakdown.ALLOW}`} tone="success" />
            <StatusBadge label={`Mask ${result.action_breakdown.MASK}`} tone="warning" />
            <StatusBadge label={`Block ${result.action_breakdown.BLOCK}`} tone="danger" />
          </div>

          {result.runtime_warnings.length > 0 ? (
            <AppAlert
              description={
                <div className="space-y-1">
                  {result.runtime_warnings.map((warning) => (
                    <p key={warning}>{warning}</p>
                  ))}
                </div>
              }
              title="Runtime warnings"
              variant="warning"
            />
          ) : null}

          <div className="overflow-x-auto rounded-xl border border-border/80">
            <table className="w-full min-w-[720px] text-sm">
              <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">Input</th>
                  <th className="px-3 py-2">Expected</th>
                  <th className="px-3 py-2">Predicted action</th>
                  <th className="px-3 py-2">Result</th>
                </tr>
              </thead>
              <tbody>
                {result.results.map((item, index) => (
                  <tr className="border-t border-border/70 align-top" key={`${index}-${item.content}`}>
                    <td className="px-3 py-3 text-sm text-foreground">
                      <HighlightedText terms={highlightTerms} text={item.content} />
                    </td>
                    <td className="px-3 py-3">
                      <StatusBadge
                        label={normalizedExpectedAction || "Review"}
                        tone={toActionTone(normalizedExpectedAction)}
                      />
                    </td>
                    <td className="px-3 py-3">
                      <StatusBadge
                        label={item.predicted_action}
                        tone={toActionTone(item.predicted_action)}
                      />
                    </td>
                    <td className="px-3 py-3">
                      {(() => {
                        const passes =
                          normalizedExpectedAction.length > 0
                            ? item.predicted_action === normalizedExpectedAction
                            : item.matched;

                        return (
                          <StatusBadge
                            label={passes ? "PASS" : "FAIL"}
                            tone={passes ? "success" : "danger"}
                          />
                        );
                      })()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </AppSectionCard>
      ) : null}
    </div>
  );
}
