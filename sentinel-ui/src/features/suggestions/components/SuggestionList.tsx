import { AlertTriangle } from "lucide-react";
import { SuggestionItem } from "@/features/suggestions/components/SuggestionItem";
import { Card } from "@/shared/ui/card";
import type { RuleSuggestionOut } from "@/features/suggestions/types";

type SuggestionListProps = {
  items: RuleSuggestionOut[];
  isLoading?: boolean;
  isError?: boolean;
  errorMessage?: string;
  onOpen: (id: string) => void;
};

export function SuggestionList({
  items,
  isLoading = false,
  isError = false,
  errorMessage,
  onOpen,
}: SuggestionListProps) {
  if (isLoading) {
    return (
      <Card className="p-4 text-sm text-muted-foreground">Loading suggestions...</Card>
    );
  }

  if (isError) {
    return (
      <Card className="flex items-start gap-2 border-destructive/30 p-4 text-sm text-destructive">
        <AlertTriangle className="mt-0.5 h-4 w-4" />
        <span>{errorMessage ?? "Failed to load suggestions."}</span>
      </Card>
    );
  }

  if (items.length === 0) {
    return (
      <Card className="p-6 text-center">
        <p className="text-sm font-medium">No suggestions yet</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Generate a suggestion to start review workflow.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-2">
      {items.map((item) => (
        <SuggestionItem item={item} key={item.id} onOpen={onOpen} />
      ))}
    </div>
  );
}
