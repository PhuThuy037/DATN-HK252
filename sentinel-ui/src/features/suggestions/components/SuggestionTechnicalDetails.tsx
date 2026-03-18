import type {
  RuleSuggestionGetOut,
  RuleSuggestionLogOut,
  SuggestionDuplicateCandidate,
} from "@/features/suggestions/types";
import { SuggestionLogsPanel } from "@/features/suggestions/components/SuggestionLogsPanel";
import { Card } from "@/shared/ui/card";

type SuggestionTechnicalDetailsProps = {
  suggestion: RuleSuggestionGetOut;
  logs: RuleSuggestionLogOut[];
  logsLoading: boolean;
  logsError: boolean;
  logsErrorMessage?: string;
  unsavedDraftSnapshot?: string | null;
  duplicateInsight?: {
    level?: "none" | "weak" | "strong";
    reason?: string;
    duplicateRisk?: string;
    conflictRisk?: string;
    runtimeUsable?: boolean;
    rationale?: string;
    similarRules?: SuggestionDuplicateCandidate[];
    candidates?: SuggestionDuplicateCandidate[];
  } | null;
};

export function SuggestionTechnicalDetails({
  suggestion,
  logs,
  logsLoading,
  logsError,
  logsErrorMessage,
  unsavedDraftSnapshot,
  duplicateInsight,
}: SuggestionTechnicalDetailsProps) {
  return (
    <Card className="space-y-3 p-4">
      <details>
        <summary className="cursor-pointer text-sm font-medium">Technical details</summary>
        <div className="mt-3 grid gap-2 text-xs text-muted-foreground md:grid-cols-2">
          <p>dedupe_key: {suggestion.dedupe_key}</p>
          <p>created_by: {suggestion.created_by}</p>
          <p>type: {suggestion.type}</p>
          <p>status: {suggestion.status}</p>
        </div>

        <details className="mt-3 rounded-md border p-2 text-xs">
          <summary className="cursor-pointer font-medium text-muted-foreground">
            Raw explanation JSON
          </summary>
          <pre className="mt-2 overflow-auto rounded-md bg-muted p-2 text-[11px]">
            {JSON.stringify(suggestion.explanation ?? null, null, 2)}
          </pre>
        </details>

        <details className="mt-3 rounded-md border p-2 text-xs">
          <summary className="cursor-pointer font-medium text-muted-foreground">
            Raw quality signals JSON
          </summary>
          <pre className="mt-2 overflow-auto rounded-md bg-muted p-2 text-[11px]">
            {JSON.stringify(suggestion.quality_signals ?? null, null, 2)}
          </pre>
        </details>

        {((Array.isArray(duplicateInsight?.similarRules) && duplicateInsight.similarRules.length > 0) ||
          (Array.isArray(duplicateInsight?.candidates) && duplicateInsight.candidates.length > 0)) && (
          <details className="mt-3 rounded-md border p-2 text-xs">
            <summary className="cursor-pointer font-medium text-muted-foreground">
              Duplicate candidate technical data
            </summary>
            <pre className="mt-2 overflow-auto rounded-md bg-muted p-2 text-[11px]">
              {JSON.stringify(
                {
                  level: duplicateInsight?.level,
                  reason: duplicateInsight?.reason ?? duplicateInsight?.rationale,
                  similar_rules: duplicateInsight?.similarRules ?? duplicateInsight?.candidates ?? [],
                },
                null,
                2
              )}
            </pre>
          </details>
        )}
      </details>

      <details>
        <summary className="cursor-pointer text-sm font-medium">Logs</summary>
        <div className="mt-3">
          <SuggestionLogsPanel
            errorMessage={logsErrorMessage}
            isError={logsError}
            isLoading={logsLoading}
            logs={logs}
          />
        </div>
      </details>

      {unsavedDraftSnapshot && (
        <details className="rounded-md border p-2 text-xs">
          <summary className="cursor-pointer font-medium text-muted-foreground">
            Unsaved local draft snapshot
          </summary>
          <pre className="mt-2 overflow-auto rounded-md bg-muted p-2 text-[11px]">
            {unsavedDraftSnapshot}
          </pre>
        </details>
      )}
    </Card>
  );
}
