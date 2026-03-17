import { Badge } from "@/shared/ui/badge";
import { cn } from "@/shared/lib/utils";
import type { PolicyIngestStatus } from "@/features/policies/types";

const statusClass: Record<PolicyIngestStatus, string> = {
  pending: "bg-amber-100 text-amber-700 border-amber-200",
  running: "bg-sky-100 text-sky-700 border-sky-200",
  success: "bg-emerald-100 text-emerald-700 border-emerald-200",
  failed: "bg-rose-100 text-rose-700 border-rose-200",
  skipped: "bg-zinc-200 text-zinc-700 border-zinc-300",
};

export function PolicyStatusBadge({ status }: { status: PolicyIngestStatus }) {
  return <Badge className={cn("border font-medium", statusClass[status])}>{status}</Badge>;
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
