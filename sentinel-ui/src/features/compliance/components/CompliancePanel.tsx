import { useMemo } from "react";
import { useMessageDetail } from "@/features/messages/hooks/useMessageDetail";
import { useChatUiStore } from "@/features/messages/store/chatUiStore";
import { Badge } from "@/shared/ui/badge";
import { Card } from "@/shared/ui/card";

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

export function CompliancePanel({
  conversationId,
  className,
}: CompliancePanelProps) {
  const selectedMessageId = useChatUiStore((state) => state.selectedMessageId);

  const detailQuery = useMessageDetail(conversationId, selectedMessageId);

  const matchedRuleIds = useMemo(
    () => detailQuery.data?.matched_rule_ids ?? [],
    [detailQuery.data?.matched_rule_ids]
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
              <div className="flex flex-wrap gap-1">
                {matchedRuleIds.length === 0 && <span>-</span>}
                {matchedRuleIds.map((ruleId) => (
                  <Badge key={ruleId}>{ruleId}</Badge>
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
