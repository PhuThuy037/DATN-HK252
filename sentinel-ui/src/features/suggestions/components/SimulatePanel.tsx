import { useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { Textarea } from "@/shared/ui/textarea";
import type { RuleSuggestionSimulateOut } from "@/features/suggestions/types";

type SimulatePanelProps = {
  disabled?: boolean;
  isSubmitting?: boolean;
  errorMessage?: string | null;
  result?: RuleSuggestionSimulateOut | null;
  onSimulate: (payload: { samples: string[]; include_examples: boolean }) => Promise<void> | void;
};

function parseSamples(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function SimulatePanel({
  disabled = false,
  isSubmitting = false,
  errorMessage,
  result,
  onSimulate,
}: SimulatePanelProps) {
  const [samplesInput, setSamplesInput] = useState("");
  const [includeExamples, setIncludeExamples] = useState(true);
  const [validationError, setValidationError] = useState<string | null>(null);

  const sampleCount = useMemo(() => parseSamples(samplesInput).length, [samplesInput]);

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
      <Card className="space-y-3 p-4">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-semibold">Simulation input</p>
          <span className="text-xs text-muted-foreground">Samples: {sampleCount}</span>
        </div>

        <Textarea
          className="min-h-[150px]"
          disabled={disabled}
          onChange={(event) => setSamplesInput(event.target.value)}
          placeholder="One sample per line"
          value={samplesInput}
        />

        <label className="inline-flex items-center gap-2 text-xs text-muted-foreground">
          <input
            checked={includeExamples}
            disabled={disabled}
            onChange={(event) => setIncludeExamples(event.target.checked)}
            type="checkbox"
          />
          include_examples
        </label>

        {validationError && (
          <p className="text-xs text-destructive">{validationError}</p>
        )}

        {errorMessage && (
          <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            <AlertTriangle className="mt-0.5 h-4 w-4" />
            <span>{errorMessage}</span>
          </div>
        )}

        <div className="flex justify-end">
          <Button disabled={disabled || isSubmitting} onClick={() => void handleSimulate()} type="button">
            {isSubmitting ? "Simulating..." : "Simulate"}
          </Button>
        </div>
      </Card>

      {result && (
        <Card className="space-y-3 p-4">
          <p className="text-sm font-semibold">Simulation result</p>
          <div className="grid gap-2 text-sm md:grid-cols-2">
            <p>sample_size: {result.sample_size}</p>
            <p>matched_count: {result.matched_count}</p>
            <p>
              action_breakdown: ALLOW {result.action_breakdown.ALLOW}, MASK {result.action_breakdown.MASK}, BLOCK {result.action_breakdown.BLOCK}
            </p>
            <p>runtime_usable: {result.runtime_usable ? "true" : "false"}</p>
          </div>

          {result.runtime_warnings.length > 0 && (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
              {result.runtime_warnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          )}

          <div className="overflow-x-auto rounded-md border">
            <table className="w-full min-w-[620px] text-sm">
              <thead className="bg-muted/40 text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">content</th>
                  <th className="px-3 py-2">matched</th>
                  <th className="px-3 py-2">predicted_action</th>
                </tr>
              </thead>
              <tbody>
                {result.results.map((item, index) => (
                  <tr className="border-t align-top" key={`${index}-${item.content}`}>
                    <td className="px-3 py-2 text-xs">{item.content}</td>
                    <td className="px-3 py-2">
                      <Badge>{item.matched ? "YES" : "NO"}</Badge>
                    </td>
                    <td className="px-3 py-2">
                      <Badge>{item.predicted_action}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
