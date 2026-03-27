import { StatusBadge as AppStatusBadge } from "@/shared/ui/status-badge";
import type { SuggestionStatus } from "@/features/suggestions/types";

export function StatusBadge({ status }: { status: SuggestionStatus }) {
  return <AppStatusBadge status={status} />;
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
