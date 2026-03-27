import { formatDate, shortId } from "@/features/suggestions/components/StatusBadge";

type SuggestionStatusSummaryProps = {
  suggestionId: string;
  createdAt?: string | null;
  updatedAt?: string | null;
  expiresAt?: string | null;
};

export function SuggestionStatusSummary({
  suggestionId,
  createdAt,
  updatedAt,
  expiresAt,
}: SuggestionStatusSummaryProps) {
  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-border/70 bg-background px-4 py-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Created</p>
          <p className="mt-1 text-sm font-medium text-foreground">{formatDate(createdAt)}</p>
        </div>
        <div className="rounded-xl border border-border/70 bg-background px-4 py-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Updated</p>
          <p className="mt-1 text-sm font-medium text-foreground">{formatDate(updatedAt)}</p>
        </div>
        <div className="rounded-xl border border-border/70 bg-background px-4 py-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Expires</p>
          <p className="mt-1 text-sm font-medium text-foreground">{formatDate(expiresAt)}</p>
        </div>
      </div>

      <p className="text-xs text-muted-foreground">Suggestion reference {shortId(suggestionId, 12)}</p>
    </div>
  );
}
