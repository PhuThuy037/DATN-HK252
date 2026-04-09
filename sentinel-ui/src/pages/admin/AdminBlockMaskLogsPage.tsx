import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getAdminBlockMaskLogs } from "@/features/admin-monitoring/api/adminMonitoringApi";
import { MatchedRulesList } from "@/features/admin-monitoring/components/MatchedRulesList";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppLoadingState } from "@/shared/ui/app-loading-state";
import { AppPageHeader } from "@/shared/ui/app-page-header";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { StatusBadge } from "@/shared/ui/status-badge";

function formatDateTime(value?: string | null) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString();
}

export function AdminBlockMaskLogsPage() {
  const [action, setAction] = useState<"all" | "mask" | "block">("all");

  const logsQuery = useQuery({
    queryKey: ["admin-block-mask-logs", action],
    queryFn: () =>
      getAdminBlockMaskLogs({
        limit: 100,
        action: action === "all" ? undefined : action,
      }),
  });

  const items = useMemo(() => logsQuery.data?.data ?? [], [logsQuery.data?.data]);
  const total = logsQuery.data?.meta?.total ?? items.length;

  return (
    <section className="h-full overflow-auto p-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4">
        <AppPageHeader
          title="Block & Mask Logs"
          subtitle="Review system-wide moderation cases that were blocked or masked by the guard runtime, with raw blocked content available only on admin surfaces."
          meta={`Showing ${items.length} of ${total} policy cases`}
        />

        <AppSectionCard
          description="Switch between all sensitive actions, only masked cases, or only blocked cases."
          title="Filters"
        >
          <div className="flex flex-wrap gap-2">
            {(["all", "mask", "block"] as const).map((value) => (
              <button
                className={`rounded-xl border px-3 py-2 text-sm ${
                  action === value
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-background text-foreground"
                }`}
                key={value}
                onClick={() => setAction(value)}
                type="button"
              >
                {value === "all" ? "All" : value === "mask" ? "Masked only" : "Blocked only"}
              </button>
            ))}
          </div>
        </AppSectionCard>

        {logsQuery.isLoading ? (
          <AppLoadingState
            className="mx-auto w-full max-w-3xl"
            description="Loading moderation outcomes across the system."
            title="Loading logs"
          />
        ) : null}

        {logsQuery.isError ? (
          <AppAlert
            description="Unable to load block and mask cases."
            title="Logs unavailable"
            variant="error"
          />
        ) : null}

        {!logsQuery.isLoading && !logsQuery.isError ? (
          <div className="grid gap-4">
            {items.length === 0 ? (
              <AppSectionCard
                description="No moderation cases matched the selected filter."
                title="No log entries"
              />
            ) : (
              items.map((item) => (
                <AppSectionCard
                  description={`Message ID: ${item.message_id}`}
                  key={item.message_id}
                  title={item.summary?.trim() || `${item.action.toUpperCase()} case`}
                  actions={
                    <Link to={`/app/admin/conversations/${item.conversation_id}`}>
                      <span className="inline-flex h-10 items-center rounded-xl border border-border bg-background px-4 text-sm font-medium">
                        Open conversation
                      </span>
                    </Link>
                  }
                >
                  <div className="grid gap-3 text-sm text-muted-foreground md:grid-cols-2 xl:grid-cols-4">
                    <div>
                      <p className="text-xs uppercase tracking-[0.12em]">Owner</p>
                      <p className="mt-1 font-medium text-foreground">
                        {item.user_name?.trim() || "Unnamed user"}
                      </p>
                      <p>{item.user_email}</p>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-[0.12em]">Decision</p>
                      <div className="mt-1 flex flex-wrap gap-2">
                        <StatusBadge status={item.action} />
                        <StatusBadge label={item.role} tone="muted" />
                        <StatusBadge
                          label={`Risk ${typeof item.risk_score === "number" ? item.risk_score.toFixed(2) : "-"}`}
                          tone="muted"
                        />
                      </div>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-[0.12em]">Conversation</p>
                      <p className="mt-1">{item.conversation_title?.trim() || "Untitled conversation"}</p>
                      <p>{item.conversation_id}</p>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-[0.12em]">Timestamp</p>
                      <p className="mt-1">{formatDateTime(item.created_at)}</p>
                    </div>
                  </div>

                  <div className="rounded-xl border border-border/70 bg-muted/20 p-3 text-sm leading-6 text-foreground">
                    {item.content ?? item.content_masked ?? "(hidden)"}
                  </div>

                  <div className="mt-3 rounded-2xl border border-border/80 bg-muted/10 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-foreground">
                          Rule match summary
                        </p>
                        <p className="mt-1 text-sm text-muted-foreground">
                          {item.summary?.trim() || "Review the matched rule list below for the rule that caused this moderation action."}
                        </p>
                      </div>
                      <StatusBadge
                        label={`${Array.isArray(item.matched_rules) ? item.matched_rules.length : 0} matched`}
                        tone="primary"
                      />
                    </div>

                    <div className="mt-4">
                      <MatchedRulesList
                        compact
                        rules={item.matched_rules}
                        emptyMessage="No structured matched rule payload was stored for this moderation case."
                      />
                    </div>
                  </div>
                </AppSectionCard>
              ))
            )}
          </div>
        ) : null}
      </div>
    </section>
  );
}
