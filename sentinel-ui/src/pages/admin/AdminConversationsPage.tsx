import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { getAdminConversations } from "@/features/admin-monitoring/api/adminMonitoringApi";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppLoadingState } from "@/shared/ui/app-loading-state";
import { AppPageHeader } from "@/shared/ui/app-page-header";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { AppButton } from "@/shared/ui/app-button";
import { Input } from "@/shared/ui/input";
import { StatusBadge } from "@/shared/ui/status-badge";

function formatDateTime(value?: string | null) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString();
}

export function AdminConversationsPage() {
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"all" | "active" | "archived">("all");

  const conversationsQuery = useQuery({
    queryKey: ["admin-conversations", search, status],
    queryFn: () =>
      getAdminConversations({
        limit: 50,
        q: search || undefined,
        status: status === "all" ? undefined : status,
      }),
  });

  const items = useMemo(
    () => conversationsQuery.data?.data ?? [],
    [conversationsQuery.data?.data]
  );
  const total = conversationsQuery.data?.meta?.total ?? items.length;

  return (
    <section className="h-full overflow-auto p-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4">
        <AppPageHeader
          title="Admin Conversation Monitoring"
          subtitle="Inspect conversations across the system, review owners, and jump into compliance details."
          meta={`Showing ${items.length} of ${total} conversations`}
        />

        <AppSectionCard
          description="Search by conversation ID, owner email, owner name, or conversation title."
          title="Filters"
        >
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px_auto]">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                className="pl-9"
                onChange={(event) => setSearchDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    setSearch(searchDraft.trim());
                  }
                }}
                placeholder="Search conversations or owners"
                value={searchDraft}
              />
            </div>
            <select
              className="h-11 rounded-xl border border-border bg-background px-3 text-sm"
              onChange={(event) =>
                setStatus(event.target.value as "all" | "active" | "archived")
              }
              value={status}
            >
              <option value="all">All statuses</option>
              <option value="active">Active</option>
              <option value="archived">Archived</option>
            </select>
            <div className="flex gap-2">
              <AppButton onClick={() => setSearch(searchDraft.trim())} type="button">
                Apply
              </AppButton>
              <AppButton
                onClick={() => {
                  setSearchDraft("");
                  setSearch("");
                  setStatus("all");
                }}
                type="button"
                variant="secondary"
              >
                Reset
              </AppButton>
            </div>
          </div>
        </AppSectionCard>

        {conversationsQuery.isLoading ? (
          <AppLoadingState
            className="mx-auto w-full max-w-3xl"
            description="Loading conversation monitoring data."
            title="Loading conversations"
          />
        ) : null}

        {conversationsQuery.isError ? (
          <AppAlert
            description="Unable to load admin conversation monitoring data."
            title="Monitoring unavailable"
            variant="error"
          />
        ) : null}

        {!conversationsQuery.isLoading && !conversationsQuery.isError ? (
          <div className="grid gap-4">
            {items.length === 0 ? (
              <AppSectionCard
                description="No conversations match the current filters."
                title="No monitoring results"
              />
            ) : (
              items.map((item) => (
                <AppSectionCard
                  description={`Conversation ID: ${item.id}`}
                  key={item.id}
                  title={item.title?.trim() || "Untitled conversation"}
                  actions={
                    <Link
                      className="inline-flex h-10 items-center rounded-xl border border-primary bg-primary px-4 text-sm font-medium text-primary-foreground"
                      to={`/app/admin/conversations/${item.id}`}
                    >
                      Open detail
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
                      <p className="text-xs uppercase tracking-[0.12em]">Status</p>
                      <div className="mt-1 flex items-center gap-2">
                        <StatusBadge status={item.status} />
                        {item.has_sensitive_action ? (
                          <StatusBadge
                            label={`${item.block_count} block / ${item.mask_count} mask`}
                            tone="warning"
                          />
                        ) : (
                          <StatusBadge label="No block/mask" tone="success" />
                        )}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-[0.12em]">Activity</p>
                      <p className="mt-1">Updated: {formatDateTime(item.updated_at)}</p>
                      <p>Created: {formatDateTime(item.created_at)}</p>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-[0.12em]">Messages</p>
                      <p className="mt-1">{item.message_count} total</p>
                      <p>Last preview: {item.last_message_preview?.trim() || "-"}</p>
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
