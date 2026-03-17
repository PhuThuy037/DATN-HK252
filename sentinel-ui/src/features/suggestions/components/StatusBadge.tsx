import { cn } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import type { SuggestionStatus } from "@/features/suggestions/types";

const statusLabel: Record<SuggestionStatus, string> = {
  draft: "Draft",
  approved: "Approved",
  applied: "Applied",
  rejected: "Rejected",
  expired: "Expired",
  failed: "Failed",
};

const statusClass: Record<SuggestionStatus, string> = {
  draft: "bg-sky-100 text-sky-700 border-sky-200",
  approved: "bg-emerald-100 text-emerald-700 border-emerald-200",
  applied: "bg-indigo-100 text-indigo-700 border-indigo-200",
  rejected: "bg-rose-100 text-rose-700 border-rose-200",
  expired: "bg-amber-100 text-amber-700 border-amber-200",
  failed: "bg-zinc-200 text-zinc-700 border-zinc-300",
};

export function StatusBadge({ status }: { status: SuggestionStatus }) {
  return (
    <Badge className={cn("border font-medium", statusClass[status])}>
      {statusLabel[status]}
    </Badge>
  );
}

export function formatDate(value?: string | null) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export function shortId(value: string, head = 8) {
  if (!value) {
    return "-";
  }
  if (value.length <= head) {
    return value;
  }
  return value.slice(0, head);
}

export function canSimulate(status: SuggestionStatus) {
  return status === "draft" || status === "approved";
}

export function canEditDraft(status: SuggestionStatus) {
  return status === "draft";
}

export function canConfirm(status: SuggestionStatus) {
  return status === "draft";
}

export function canReject(status: SuggestionStatus) {
  return status === "draft" || status === "approved";
}

export function canApply(status: SuggestionStatus) {
  return status === "approved";
}
