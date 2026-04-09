import type { AdminMatchedRule } from "@/features/admin-monitoring/types/adminMonitoringTypes";
import { StatusBadge } from "@/shared/ui/status-badge";

type MatchedRulesListProps = {
  rules?: AdminMatchedRule[] | null;
  compact?: boolean;
  emptyMessage?: string;
};

function normalizeRule(rule: AdminMatchedRule) {
  return {
    ruleId: String(rule.rule_id ?? "").trim(),
    stableKey: String(rule.stable_key ?? "").trim(),
    name: String(rule.name ?? "").trim(),
    action: String(rule.action ?? "").trim().toLowerCase(),
    priority:
      typeof rule.priority === "number" && Number.isFinite(rule.priority)
        ? rule.priority
        : null,
  };
}

export function MatchedRulesList({
  rules,
  compact = false,
  emptyMessage = "No matched rules recorded for this message.",
}: MatchedRulesListProps) {
  const items = (rules ?? []).map(normalizeRule).filter((rule) => {
    return Boolean(
      rule.ruleId || rule.stableKey || rule.name || rule.action || rule.priority !== null
    );
  });

  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border/80 bg-muted/10 px-4 py-3 text-sm text-muted-foreground">
        {emptyMessage}
      </div>
    );
  }

  if (compact) {
    return (
      <div className="space-y-2">
        {items.map((rule, index) => (
          <div
            className="rounded-xl border border-border/70 bg-background px-3 py-3"
            key={`${rule.ruleId || rule.stableKey || rule.name || "rule"}-${index}`}
          >
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-semibold text-foreground">
                {rule.name || "Unnamed rule"}
              </p>
              {rule.action ? <StatusBadge status={rule.action} /> : null}
              {rule.priority !== null ? (
                <StatusBadge label={`P${rule.priority}`} tone="muted" />
              ) : null}
            </div>
            <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
              {rule.stableKey ? <span>Key: <code>{rule.stableKey}</code></span> : null}
              {rule.ruleId ? <span>ID: <code>{rule.ruleId}</code></span> : null}
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {items.map((rule, index) => (
        <div
          className="rounded-2xl border border-border/80 bg-background p-4"
          key={`${rule.ruleId || rule.stableKey || rule.name || "rule"}-${index}`}
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-foreground">
                {rule.name || "Unnamed rule"}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {rule.stableKey ? <span>Stable key: <code>{rule.stableKey}</code></span> : "Stable key unavailable"}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {rule.action ? <StatusBadge status={rule.action} /> : null}
              {rule.priority !== null ? (
                <StatusBadge label={`Priority ${rule.priority}`} tone="muted" />
              ) : null}
            </div>
          </div>

          <div className="mt-3 grid gap-3 text-xs text-muted-foreground md:grid-cols-2">
            <div>
              <p className="uppercase tracking-[0.12em]">Rule ID</p>
              <p className="mt-1 break-all font-mono text-[11px] text-foreground/80">
                {rule.ruleId || "-"}
              </p>
            </div>
            <div>
              <p className="uppercase tracking-[0.12em]">Decision</p>
              <p className="mt-1 text-foreground/80">
                {rule.action ? rule.action.toUpperCase() : "Unavailable"}
              </p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
