import { AlertTriangle } from "lucide-react";
import { SuggestionItem } from "@/features/suggestions/components/SuggestionItem";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppLoadingState } from "@/shared/ui/app-loading-state";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { EmptyState } from "@/shared/ui/empty-state";
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
      <AppLoadingState
        compact
        description="Loading the latest suggestions for this workspace."
        title="Loading suggestions"
      />
    );
  }

  if (isError) {
    return (
      <AppAlert
        description={errorMessage ?? "Failed to load suggestions."}
        icon={<AlertTriangle className="mt-0.5 h-4 w-4 text-danger" />}
        title="Unable to load suggestions"
        variant="error"
      />
    );
  }

  if (items.length === 0) {
    return (
      <EmptyState
        description="Generate a suggestion to start the review workflow."
        title="No suggestions yet"
      />
    );
  }

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <SuggestionItem item={item} key={item.id} onOpen={onOpen} />
      ))}
    </div>
  );
}
