import { Card } from "@/shared/ui/card";
import { StatusBadge, formatDate, shortId } from "@/features/suggestions/components/StatusBadge";
import type { RuleSuggestionOut } from "@/features/suggestions/types";

type SuggestionItemProps = {
  item: RuleSuggestionOut;
  onOpen: (id: string) => void;
};

function truncate(text: string, max = 90) {
  const value = text.trim();
  if (value.length <= max) {
    return value;
  }
  return `${value.slice(0, max)}...`;
}

export function SuggestionItem({ item, onOpen }: SuggestionItemProps) {
  return (
    <Card
      className="cursor-pointer p-3 transition-colors hover:bg-muted/40"
      onClick={() => onOpen(item.id)}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen(item.id);
        }
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <StatusBadge status={item.status} />
          <span className="text-xs text-muted-foreground">v{item.version}</span>
        </div>
        <span className="text-xs text-muted-foreground">{formatDate(item.created_at)}</span>
      </div>

      <p className="mt-2 text-sm text-foreground">{truncate(item.nl_input)}</p>

      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <span>ID: {shortId(item.id)}</span>
        <span>Updated: {formatDate(item.updated_at)}</span>
      </div>
    </Card>
  );
}
