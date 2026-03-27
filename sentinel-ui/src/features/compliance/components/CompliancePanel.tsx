import { useMemo } from "react";
import { ShieldAlert, ShieldCheck, ShieldEllipsis } from "lucide-react";
import { useMessageDetail } from "@/features/messages/hooks/useMessageDetail";
import { useChatUiStore } from "@/features/messages/store/chatUiStore";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppLoadingState } from "@/shared/ui/app-loading-state";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { EmptyState } from "@/shared/ui/empty-state";
import { StatusBadge } from "@/shared/ui/status-badge";
import { TechnicalDetailsAccordion } from "@/shared/ui/technical-details-accordion";
import type { MessageMatchedRule } from "@/shared/types";

type CompliancePanelProps = {
  conversationId?: string;
  className?: string;
};

type ComplianceMatchedRuleItem = {
  key: string;
  displayName: string;
  stableKey?: string | null;
  ruleId?: string | null;
};

function buildMatchedRuleItems(
  matchedRules?: MessageMatchedRule[] | null,
  matchedRuleIds?: string[] | null
) {
  const items: ComplianceMatchedRuleItem[] = [];
  const seen = new Set<string>();

  for (const rule of matchedRules ?? []) {
    const ruleId = rule.rule_id?.trim() || null;
    const stableKey = rule.stable_key?.trim() || null;
    const name = rule.name?.trim() || "";
    const key = ruleId || stableKey || name;
    if (!key || seen.has(key)) {
      continue;
    }
    seen.add(key);
    items.push({
      key,
      displayName: name || stableKey || "Unnamed rule",
      stableKey,
      ruleId,
    });
  }

  for (const ruleId of matchedRuleIds ?? []) {
    const normalizedId = String(ruleId ?? "").trim();
    if (!normalizedId || seen.has(normalizedId)) {
      continue;
    }
    seen.add(normalizedId);
    items.push({
      key: normalizedId,
      displayName: "Unknown rule",
      ruleId: normalizedId,
    });
  }

  return items;
}

function normalizeAction(value?: string | null) {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (normalized === "allow" || normalized === "mask" || normalized === "block") {
    return normalized;
  }
  return null;
}

function getRiskValue(score?: number | null) {
  if (typeof score !== "number" || Number.isNaN(score)) {
    return null;
  }
  const normalized = score <= 1 ? score * 100 : score;
  return Math.max(0, Math.min(100, normalized));
}

function getRiskTone(riskValue: number | null) {
  if (riskValue == null) {
    return "muted";
  }
  if (riskValue >= 75) {
    return "danger";
  }
  if (riskValue >= 40) {
    return "warning";
  }
  return "success";
}

function formatRiskLabel(riskValue: number | null) {
  if (riskValue == null) {
    return "Unavailable";
  }
  return `${Math.round(riskValue)}/100`;
}

function formatShortRuleId(ruleId?: string | null) {
  const value = String(ruleId ?? "").trim();
  if (!value) {
    return null;
  }
  if (value.length <= 14) {
    return value;
  }
  return `${value.slice(0, 10)}...`;
}

function getActionIcon(action: "allow" | "mask" | "block" | null) {
  if (action === "allow") {
    return <ShieldCheck className="h-4 w-4 text-success" />;
  }
  if (action === "mask") {
    return <ShieldEllipsis className="h-4 w-4 text-warning" />;
  }
  if (action === "block") {
    return <ShieldAlert className="h-4 w-4 text-danger" />;
  }
  return null;
}

export function CompliancePanel({
  conversationId,
  className,
}: CompliancePanelProps) {
  const selectedMessageId = useChatUiStore((state) => state.selectedMessageId);
  const detailQuery = useMessageDetail(conversationId, selectedMessageId);

  const matchedRules = useMemo(
    () =>
      buildMatchedRuleItems(
        detailQuery.data?.matched_rules,
        detailQuery.data?.matched_rule_ids
      ),
    [detailQuery.data?.matched_rule_ids, detailQuery.data?.matched_rules]
  );

  const action = normalizeAction(detailQuery.data?.final_action);
  const riskValue = getRiskValue(detailQuery.data?.risk_score);
  const riskTone = getRiskTone(riskValue);

  return (
    <aside className={className}>
      <div className="flex h-full flex-col gap-4 overflow-y-auto rounded-[30px] border border-border/80 bg-background/88 p-4 shadow-app-md backdrop-blur lg:p-5">
        <div className="space-y-1.5">
          <h3 className="text-lg font-semibold">Compliance Detail</h3>
          <p className="text-sm text-muted-foreground">
            Review the selected message outcome and the rules that contributed to it.
          </p>
        </div>

        {!selectedMessageId && (
          <EmptyState
            description="Select a message in chat to view scan details."
            title="No message selected"
          />
        )}

        {selectedMessageId && detailQuery.isLoading && (
          <AppLoadingState
            compact
            description="Loading the selected message outcome and matched rules."
            title="Loading message detail"
          />
        )}

        {selectedMessageId && detailQuery.isError && (
          <AppAlert
            description="Failed to load compliance detail."
            title="Compliance detail unavailable"
            variant="error"
          />
        )}

        {selectedMessageId && detailQuery.data && (
          <>
            <AppSectionCard
              description="This summary highlights the final moderation outcome for the selected message."
              title="Summary"
            >
              <div className="space-y-3">
                <div className="rounded-[24px] border border-border/70 bg-muted/20 p-5">
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                    Final action
                  </p>
                  <div className="mt-4 flex items-center gap-3">
                    {getActionIcon(action)}
                    <StatusBadge
                      label={action ? undefined : detailQuery.data.final_action ?? "Unavailable"}
                      status={action ?? undefined}
                      tone={action === null ? "muted" : undefined}
                    />
                  </div>
                  <p className="mt-4 text-sm leading-6 text-muted-foreground">
                    {detailQuery.data.blocked
                      ? detailQuery.data.blocked_reason ?? "Message content was blocked."
                      : "The message was processed and recorded successfully."}
                  </p>
                </div>

                <div className="rounded-[24px] border border-border/70 bg-muted/20 p-5">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                      Risk score
                    </p>
                    <StatusBadge
                      label={formatRiskLabel(riskValue)}
                      tone={riskTone}
                    />
                  </div>
                  <div className="mt-5 h-3 overflow-hidden rounded-full bg-muted">
                    <div
                      className={
                        riskTone === "danger"
                          ? "h-full rounded-full bg-danger"
                          : riskTone === "warning"
                            ? "h-full rounded-full bg-warning"
                            : riskTone === "success"
                              ? "h-full rounded-full bg-success"
                              : "h-full rounded-full bg-muted-foreground/40"
                      }
                      style={{ width: `${riskValue ?? 0}%` }}
                    />
                  </div>
                  <div className="mt-4 grid gap-2 text-sm text-muted-foreground">
                    <p>Blocked: {detailQuery.data.blocked ? "Yes" : "No"}</p>
                    <p>Scan status: {detailQuery.data.scan_status ?? "-"}</p>
                    <p>Latency: {detailQuery.data.latency_ms ?? "-"} ms</p>
                  </div>
                </div>
              </div>
            </AppSectionCard>

            <AppSectionCard
              description="Matched rules are ordered from the message detail payload. Names are shown first, with stable keys as secondary context."
              title="Matched Rules"
            >
              {matchedRules.length === 0 ? (
                <EmptyState
                  description="No rules were attached to this message outcome."
                  title="No matched rules"
                />
              ) : (
                <div className="space-y-3">
                  {matchedRules.map((rule) => (
                    <div className="rounded-[22px] border border-border/70 bg-muted/18 px-4 py-4" key={rule.key}>
                      <p className="text-sm font-semibold text-foreground">{rule.displayName}</p>
                      {rule.stableKey ? (
                        <p className="mt-1.5 break-all text-xs leading-5 text-muted-foreground">{rule.stableKey}</p>
                      ) : rule.ruleId ? (
                        <p className="mt-1.5 text-xs leading-5 text-muted-foreground">ID: {formatShortRuleId(rule.ruleId)}</p>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </AppSectionCard>

            <TechnicalDetailsAccordion
              className="opacity-90"
              description="Raw evidence and extracted entities are available for deeper inspection."
              sections={[
                {
                  title: "Entities",
                  data: detailQuery.data.entities_json,
                },
                {
                  title: "RAG evidence",
                  data: detailQuery.data.rag_evidence_json,
                },
              ]}
              title="Technical details"
            />
          </>
        )}
      </div>
    </aside>
  );
}
