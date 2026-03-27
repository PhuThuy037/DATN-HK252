import { AppAlert } from "@/shared/ui/app-alert";
import { AppLoadingState } from "@/shared/ui/app-loading-state";
import { EmptyState } from "@/shared/ui/empty-state";
import { StatusBadge } from "@/shared/ui/status-badge";
import { TechnicalDetailsAccordion } from "@/shared/ui/technical-details-accordion";
import { Card } from "@/shared/ui/card";
import { formatDate } from "@/features/suggestions/components/StatusBadge";
import type { RuleSuggestionLogOut } from "@/features/suggestions/types";

type SuggestionLogsProps = {
  logs: RuleSuggestionLogOut[];
  isLoading?: boolean;
  isError?: boolean;
  errorMessage?: string;
};

function summarizeDiff(log: RuleSuggestionLogOut) {
  const before = log.before_json as Record<string, unknown> | null | undefined;
  const after = log.after_json as Record<string, unknown> | null | undefined;

  if (!before || !after) {
    return null;
  }

  const lines: string[] = [];
  const beforeStatus = typeof before.status === "string" ? before.status : undefined;
  const afterStatus = typeof after.status === "string" ? after.status : undefined;
  if (beforeStatus !== afterStatus) {
    lines.push(`status: ${beforeStatus ?? "-"} -> ${afterStatus ?? "-"}`);
  }

  const beforeVersion = typeof before.version === "number" ? before.version : undefined;
  const afterVersion = typeof after.version === "number" ? after.version : undefined;
  if (beforeVersion !== afterVersion) {
    lines.push(`version: ${String(beforeVersion ?? "-")} -> ${String(afterVersion ?? "-")}`);
  }

  return lines.length > 0 ? lines : null;
}

export function SuggestionLogs({
  logs,
  isLoading = false,
  isError = false,
  errorMessage,
}: SuggestionLogsProps) {
  if (isLoading) {
    return (
      <AppLoadingState
        compact
        description="Loading activity history for this suggestion."
        title="Loading logs"
      />
    );
  }

  if (isError) {
    return (
      <AppAlert
        description={errorMessage ?? "Failed to load logs."}
        title="Logs unavailable"
        variant="error"
      />
    );
  }

  if (logs.length === 0) {
    return (
      <EmptyState
        description="Activity history will appear here as this suggestion moves through the workflow."
        title="No logs yet"
      />
    );
  }

  return (
    <div className="space-y-3">
      {logs.map((log) => {
        const diffSummary = summarizeDiff(log);
        return (
          <Card className="space-y-3 p-3" key={log.id}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge label={log.action} />
                <span className="text-xs text-muted-foreground">{formatDate(log.created_at)}</span>
              </div>
              <span className="text-xs text-muted-foreground">actor: {log.actor_user_id}</span>
            </div>

            <p className="text-xs text-muted-foreground">reason: {log.reason ?? "-"}</p>

            {diffSummary && (
              <div className="rounded-md border bg-muted/30 p-2 text-xs">
                {diffSummary.map((line) => (
                  <p key={line}>{line}</p>
                ))}
              </div>
            )}

            <TechnicalDetailsAccordion
              sections={[
                {
                  title: "Before snapshot",
                  data: log.before_json ?? null,
                },
                {
                  title: "After snapshot",
                  data: log.after_json ?? null,
                },
              ]}
              title="Technical details"
            />
          </Card>
        );
      })}
    </div>
  );
}
