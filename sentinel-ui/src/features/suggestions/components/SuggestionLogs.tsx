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
    return <Card className="p-4 text-sm text-muted-foreground">Loading logs...</Card>;
  }

  if (isError) {
    return <Card className="p-4 text-sm text-destructive">{errorMessage ?? "Failed to load logs."}</Card>;
  }

  if (logs.length === 0) {
    return (
      <Card className="p-4 text-center">
        <p className="text-sm font-medium">No logs</p>
        <p className="mt-1 text-xs text-muted-foreground">No audit records available for this suggestion.</p>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {logs.map((log) => {
        const diffSummary = summarizeDiff(log);
        return (
          <Card className="space-y-3 p-3" key={log.id}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="space-x-2">
                <span className="text-sm font-semibold">{log.action}</span>
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

            <details className="rounded-md border p-2 text-xs">
              <summary className="cursor-pointer font-medium text-muted-foreground">before_json</summary>
              <pre className="mt-2 overflow-x-auto rounded bg-muted p-2 text-[11px]">
                {JSON.stringify(log.before_json ?? null, null, 2)}
              </pre>
            </details>

            <details className="rounded-md border p-2 text-xs">
              <summary className="cursor-pointer font-medium text-muted-foreground">after_json</summary>
              <pre className="mt-2 overflow-x-auto rounded bg-muted p-2 text-[11px]">
                {JSON.stringify(log.after_json ?? null, null, 2)}
              </pre>
            </details>
          </Card>
        );
      })}
    </div>
  );
}
