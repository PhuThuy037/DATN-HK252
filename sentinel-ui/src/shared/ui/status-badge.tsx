import { cn } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";

type StatusTone = "primary" | "success" | "warning" | "danger" | "muted";

type StatusBadgeProps = {
  status?: string | null;
  label?: string;
  tone?: StatusTone;
  className?: string;
};

const toneClasses: Record<StatusTone, string> = {
  primary: "border-primary/15 bg-primary/10 text-primary",
  success: "border-success-border bg-success-muted text-success",
  warning: "border-warning-border bg-warning-muted text-warning",
  danger: "border-danger-border bg-danger-muted text-danger",
  muted: "border-border bg-muted/80 text-muted-foreground",
};

const statusPresets: Record<string, { label: string; tone: StatusTone }> = {
  allow: { label: "Allow", tone: "success" },
  mask: { label: "Mask", tone: "warning" },
  block: { label: "Block", tone: "danger" },
  enabled: { label: "Enabled", tone: "success" },
  disabled: { label: "Disabled", tone: "muted" },
  draft: { label: "Draft", tone: "warning" },
  approved: { label: "Approved", tone: "success" },
  applied: { label: "Applied", tone: "primary" },
  rejected: { label: "Rejected", tone: "danger" },
  expired: { label: "Expired", tone: "warning" },
  failed: { label: "Failed", tone: "danger" },
  pending: { label: "Pending", tone: "warning" },
  running: { label: "Running", tone: "primary" },
  similar: { label: "Similar", tone: "warning" },
  "very similar": { label: "Very similar", tone: "danger" },
  "exact duplicate": { label: "Exact duplicate", tone: "danger" },
  success: { label: "Success", tone: "success" },
  skipped: { label: "Skipped", tone: "muted" },
};

function toStatusLabel(value: string) {
  return value
    .replace(/[_-]+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function StatusBadge({ status, label, tone, className }: StatusBadgeProps) {
  const normalizedStatus = String(status ?? "")
    .trim()
    .toLowerCase();
  const preset = normalizedStatus ? statusPresets[normalizedStatus] : undefined;
  const resolvedTone = tone ?? preset?.tone ?? "muted";
  const resolvedLabel = label ?? preset?.label ?? (normalizedStatus ? toStatusLabel(normalizedStatus) : "-");

  return <Badge className={cn(toneClasses[resolvedTone], className)}>{resolvedLabel}</Badge>;
}
