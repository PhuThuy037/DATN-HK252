import { useMemo } from "react";
import { useMessageDetail } from "@/features/messages/hooks/useMessageDetail";
import { useChatUiStore } from "@/features/messages/store/chatUiStore";
import { Card } from "@/shared/ui/card";
import type { MessageMatchedRule } from "@/shared/types";

type CompliancePanelProps = {
  conversationId?: string;
  className?: string;
};

function formatJson(value: unknown) {
  if (value == null) {
    return "-";
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

type ComplianceMatchedRuleItem = {
  key: string;
  name: string;
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
      name: name || "Unknown rule",
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
      name: "Unknown rule",
      ruleId: normalizedId,
    });
  }

  return items;
}

function formatShortRuleId(ruleId?: string | null) {
  const value = String(ruleId ?? "").trim();
  if (!value) {
    return null;
  }
  if (value.length <= 12) {
    return value;
  }
  return `${value.slice(0, 8)}...`;
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

  return (
    <aside className={className}>
      <Card className="h-full overflow-y-auto rounded-2xl p-4">
        <h3 className="text-sm font-semibold">Compliance Detail</h3>

        {!selectedMessageId && (
          <div className="mt-4 rounded-lg border border-dashed p-4 text-center">
            <p className="text-sm font-medium">No message selected</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Select a message in chat to view scan details.
            </p>
          </div>
        )}

        {selectedMessageId && detailQuery.isLoading && (
          <p className="mt-3 text-sm text-muted-foreground">Loading message detail...</p>
        )}

        {selectedMessageId && detailQuery.isError && (
          <p className="mt-3 text-sm text-destructive">
            Failed to load compliance detail.
          </p>
        )}

        {selectedMessageId && detailQuery.data && (
          <div className="mt-4 space-y-4 text-sm">
            <section className="rounded-xl border bg-background p-3">
              <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
                Scan Result
              </p>
              <div className="space-y-2">
                <div>
                  <p className="text-xs text-muted-foreground">Final action</p>
                  <p className="font-medium">{detailQuery.data.final_action ?? "-"}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Risk score</p>
                  <p className="font-medium">{detailQuery.data.risk_score ?? "-"}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Blocked</p>
                  <p className="font-medium">{detailQuery.data.blocked ? "Yes" : "No"}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Blocked reason</p>
                  <p className="font-medium">{detailQuery.data.blocked_reason ?? "-"}</p>
                </div>
              </div>
            </section>

            <section className="rounded-xl border bg-background p-3">
              <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
                Matched Rules
              </p>
              <div className="space-y-2">
                {matchedRules.length === 0 && (
                  <p className="text-sm text-muted-foreground">No matched rules.</p>
                )}
                {matchedRules.map((rule) => (
                  <div className="rounded-lg border bg-muted/30 p-2.5" key={rule.key}>
                    <p className="text-sm font-medium">{rule.name}</p>
                    {rule.stableKey && (
                      <p className="mt-1 break-all text-xs text-muted-foreground">
                        {rule.stableKey}
                      </p>
                    )}
                    {!rule.stableKey && rule.ruleId && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        ID: {formatShortRuleId(rule.ruleId)}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </section>

            <details className="rounded-xl border bg-background p-3">
              <summary className="cursor-pointer list-none text-xs font-semibold uppercase text-muted-foreground">
                Technical details
              </summary>

              <div className="mt-3 space-y-3">
                <div>
                  <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
                    Entities
                  </p>
                  <pre className="overflow-auto rounded-md bg-muted p-2 text-xs">
                    {formatJson(detailQuery.data.entities_json)}
                  </pre>
                </div>

                <div>
                  <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
                    RAG Evidence
                  </p>
                  <pre className="overflow-auto rounded-md bg-muted p-2 text-xs">
                    {formatJson(detailQuery.data.rag_evidence_json)}
                  </pre>
                </div>
              </div>
            </details>
          </div>
        )}
      </Card>
    </aside>
  );
}
