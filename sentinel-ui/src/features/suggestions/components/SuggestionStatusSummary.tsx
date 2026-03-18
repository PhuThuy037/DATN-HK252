import { StatusBadge, formatDate } from "@/features/suggestions/components/StatusBadge";
import type { SuggestionStatus } from "@/features/suggestions/types";

type SuggestionStatusSummaryProps = {
  status: SuggestionStatus;
  version: number;
  suggestionId: string;
  createdAt?: string | null;
  updatedAt?: string | null;
  expiresAt?: string | null;
};

export function SuggestionStatusSummary({
  status,
  version,
  suggestionId,
  createdAt,
  updatedAt,
  expiresAt,
}: SuggestionStatusSummaryProps) {
  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={status} />
        <span className="text-xs text-muted-foreground">Version {version}</span>
        <span className="text-xs text-muted-foreground">ID: {suggestionId}</span>
      </div>

      <div className="grid gap-1 text-xs text-muted-foreground md:grid-cols-3">
        <p>Created: {formatDate(createdAt)}</p>
        <p>Updated: {formatDate(updatedAt)}</p>
        <p>Expires: {formatDate(expiresAt)}</p>
      </div>
    </>
  );
}
