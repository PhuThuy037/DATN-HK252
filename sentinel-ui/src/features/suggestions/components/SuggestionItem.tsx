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

function getSuggestionTitle(item: RuleSuggestionOut) {
  const ruleName = item.draft?.rule?.name?.trim();
  if (ruleName) {
    return truncate(ruleName, 72);
  }
  return truncate(item.nl_input, 72);
}

export function SuggestionItem({ item, onOpen }: SuggestionItemProps) {
  const title = getSuggestionTitle(item);
  const promptPreview = truncate(item.nl_input, 160);

  return (
    <Card
      className="group cursor-pointer space-y-4 p-4 transition-all hover:-translate-y-0.5 hover:border-primary/20 hover:shadow-app-md md:p-5"
      onClick={() => onOpen(item.id)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen(item.id);
        }
      }}
      role="button"
      tabIndex={0}
    >
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={item.status} />
            <span className="text-xs font-medium text-muted-foreground">Version {item.version}</span>
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-semibold text-foreground transition-colors group-hover:text-primary">
              {title}
            </h3>
            <p className="text-sm leading-6 text-muted-foreground">{promptPreview}</p>
          </div>
        </div>

        <div className="grid gap-1 text-xs text-muted-foreground md:min-w-[180px] md:text-right">
          <span>Updated {formatDate(item.updated_at)}</span>
          <span>Created {formatDate(item.created_at)}</span>
          {item.expires_at ? <span>Expires {formatDate(item.expires_at)}</span> : null}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t border-border/70 pt-3 text-xs text-muted-foreground">
        <span>Rule: {item.draft?.rule?.stable_key?.trim() || item.draft?.rule?.name?.trim() || "Draft rule"}</span>
        <span className="text-[11px]">Ref {shortId(item.id)}</span>
      </div>
    </Card>
  );
}
