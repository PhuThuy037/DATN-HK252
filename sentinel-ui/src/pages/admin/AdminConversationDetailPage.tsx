import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getAdminConversation, getAdminConversationMessages } from "@/features/admin-monitoring/api/adminMonitoringApi";
import type { AdminMessageDetail } from "@/features/admin-monitoring/types/adminMonitoringTypes";
import { MatchedRulesList } from "@/features/admin-monitoring/components/MatchedRulesList";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppLoadingState } from "@/shared/ui/app-loading-state";
import { AppPageHeader } from "@/shared/ui/app-page-header";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { StatusBadge } from "@/shared/ui/status-badge";
import { TechnicalDetailsAccordion } from "@/shared/ui/technical-details-accordion";

function formatDateTime(value?: string | null) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString();
}

function getMessageBody(message: AdminMessageDetail) {
  return message.content ?? message.content_masked ?? "(hidden)";
}

function getDecisionSummary(message: AdminMessageDetail) {
  const action = String(message.final_action ?? "").trim().toLowerCase();
  const matchedCount = Array.isArray(message.matched_rules)
    ? message.matched_rules.length
    : Array.isArray(message.matched_rule_ids)
      ? message.matched_rule_ids.length
      : 0;

  if (action === "block") {
    return matchedCount > 0
      ? `Blocked after matching ${matchedCount} rule${matchedCount > 1 ? "s" : ""}.`
      : "Blocked by active compliance policy.";
  }
  if (action === "mask") {
    return matchedCount > 0
      ? `Masked after matching ${matchedCount} rule${matchedCount > 1 ? "s" : ""}.`
      : "Masked by active compliance policy.";
  }
  if (matchedCount > 0) {
    return `Allowed after evaluating ${matchedCount} matched rule${matchedCount > 1 ? "s" : ""}.`;
  }
  return "No matched rules were recorded for this message.";
}

export function AdminConversationDetailPage() {
  const { conversationId } = useParams();

  const detailQuery = useQuery({
    queryKey: ["admin-conversation-detail", conversationId],
    queryFn: () => getAdminConversation(conversationId!),
    enabled: Boolean(conversationId),
  });

  const messagesQuery = useQuery({
    queryKey: ["admin-conversation-messages", conversationId],
    queryFn: () =>
      getAdminConversationMessages(conversationId!, {
        limit: 100,
      }),
    enabled: Boolean(conversationId),
  });

  const messages = useMemo(
    () => messagesQuery.data?.items ?? [],
    [messagesQuery.data?.items]
  );

  return (
    <section className="h-full overflow-auto p-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4">
        <AppPageHeader
          title={detailQuery.data?.title?.trim() || "Conversation detail"}
          subtitle="Review metadata, owner context, and full compliance detail for every message in this conversation, including raw blocked content for admin monitoring."
          meta={conversationId ? `Conversation ID: ${conversationId}` : undefined}
          actions={
            <Link
              className="inline-flex h-10 items-center rounded-xl border border-border bg-background px-4 text-sm font-medium text-foreground"
              to="/app/admin/conversations"
            >
              Back to monitoring
            </Link>
          }
        />

        {detailQuery.isLoading ? (
          <AppLoadingState
            className="mx-auto w-full max-w-3xl"
            description="Loading conversation monitoring detail."
            title="Loading conversation"
          />
        ) : null}

        {detailQuery.isError ? (
          <AppAlert
            description="Unable to load conversation detail."
            title="Conversation unavailable"
            variant="error"
          />
        ) : null}

        {detailQuery.data ? (
          <AppSectionCard
            description="Owner and moderation counters are shown here for quick triage."
            title="Conversation metadata"
          >
            <div className="grid gap-3 text-sm text-muted-foreground md:grid-cols-2 xl:grid-cols-4">
              <div>
                <p className="text-xs uppercase tracking-[0.12em]">Owner</p>
                <p className="mt-1 font-medium text-foreground">
                  {detailQuery.data.user_name?.trim() || "Unnamed user"}
                </p>
                <p>{detailQuery.data.user_email}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.12em]">Conversation</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  <StatusBadge status={detailQuery.data.status} />
                  <StatusBadge label={`${detailQuery.data.message_count} messages`} tone="primary" />
                </div>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.12em]">Sensitive actions</p>
                <p className="mt-1">{detailQuery.data.block_count} blocked</p>
                <p>{detailQuery.data.mask_count} masked</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.12em]">Timestamps</p>
                <p className="mt-1">Created: {formatDateTime(detailQuery.data.created_at)}</p>
                <p>Updated: {formatDateTime(detailQuery.data.updated_at)}</p>
              </div>
            </div>
          </AppSectionCard>
        ) : null}

        {messagesQuery.isLoading ? (
          <AppLoadingState
            className="mx-auto w-full max-w-3xl"
            description="Loading message timeline and compliance metadata."
            title="Loading messages"
          />
        ) : null}

        {messagesQuery.isError ? (
          <AppAlert
            description="Unable to load message timeline."
            title="Messages unavailable"
            variant="error"
          />
        ) : null}

        {!messagesQuery.isLoading && !messagesQuery.isError ? (
          <AppSectionCard
            description="Admin monitoring shows the persisted message timeline, including raw blocked content that remains hidden from user-facing chat APIs."
            title="Conversation messages"
          >
            <div className="space-y-4">
              {messages.length === 0 ? (
                <p className="text-sm text-muted-foreground">No messages recorded for this conversation.</p>
              ) : (
                messages.map((message) => (
                  <div className="rounded-2xl border border-border/80 bg-background p-4" key={message.id}>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-foreground">
                          {message.role.toUpperCase()} #{message.sequence_number}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {formatDateTime(message.created_at)}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <StatusBadge status={message.final_action ?? undefined} label={message.final_action ?? "allow"} />
                        <StatusBadge label={`Risk ${typeof message.risk_score === "number" ? message.risk_score.toFixed(2) : "-"}`} tone="muted" />
                      </div>
                    </div>

                    <div className="mt-3 rounded-xl border border-border/70 bg-muted/20 p-3 text-sm leading-6 text-foreground">
                      {getMessageBody(message)}
                    </div>

                    <div className="mt-3 rounded-2xl border border-border/80 bg-muted/10 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-foreground">Compliance summary</p>
                          <p className="mt-1 text-sm text-muted-foreground">
                            {getDecisionSummary(message)}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <StatusBadge
                            label={`${Array.isArray(message.matched_rules) ? message.matched_rules.length : 0} matched`}
                            tone="primary"
                          />
                          <StatusBadge
                            label={`Risk ${typeof message.risk_score === "number" ? message.risk_score.toFixed(2) : "-"}`}
                            tone="muted"
                          />
                        </div>
                      </div>

                      <div className="mt-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                          Matched rules
                        </p>
                        <div className="mt-2">
                          <MatchedRulesList
                            rules={message.matched_rules}
                            emptyMessage="This message has no matched rule objects. Expand raw debug data if you need the original payload."
                          />
                        </div>
                      </div>
                    </div>

                    <TechnicalDetailsAccordion
                      className="mt-3"
                      defaultOpen={false}
                      description="Use the debug sections below when you need the original compliance payload or supporting metadata."
                      sections={[
                        {
                          title: "Raw matched rules JSON",
                          data: message.matched_rules ?? message.matched_rule_ids ?? [],
                        },
                        {
                          title: "Entities JSON",
                          data: message.entities_json ?? {},
                        },
                        {
                          title: "RAG evidence JSON",
                          data: message.rag_evidence_json ?? {},
                        },
                      ]}
                      title="Compliance detail"
                    />
                  </div>
                ))
              )}
            </div>
          </AppSectionCard>
        ) : null}
      </div>
    </section>
  );
}
