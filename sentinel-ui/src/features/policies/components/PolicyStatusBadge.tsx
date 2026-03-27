import { StatusBadge } from "@/shared/ui/status-badge";
import type { PolicyIngestStatus } from "@/features/policies/types";

export function PolicyStatusBadge({ status }: { status: PolicyIngestStatus }) {
  return <StatusBadge status={status} />;
}

export function formatPolicyDate(value?: string | null) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export function shortPolicyId(value: string, head = 8) {
  if (!value) {
    return "-";
  }
  return value.slice(0, head);
}
