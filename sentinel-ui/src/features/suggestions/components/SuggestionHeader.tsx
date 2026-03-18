import { ArrowLeft } from "lucide-react";
import { SuggestionStatusSummary } from "@/features/suggestions/components/SuggestionStatusSummary";
import type { SuggestionStatus } from "@/features/suggestions/types";
import { Button } from "@/shared/ui/button";

type SuggestionHeaderProps = {
  title: string;
  status: SuggestionStatus;
  version: number;
  suggestionId: string;
  createdAt?: string | null;
  updatedAt?: string | null;
  expiresAt?: string | null;
  onBack: () => void;
};

export function SuggestionHeader({
  title,
  status,
  version,
  suggestionId,
  createdAt,
  updatedAt,
  expiresAt,
  onBack,
}: SuggestionHeaderProps) {
  return (
    <div className="space-y-3">
      <Button onClick={onBack} size="sm" type="button" variant="outline">
        <ArrowLeft className="mr-1 h-4 w-4" />
        Back
      </Button>

      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Rule suggestion</p>
        <h1 className="text-lg font-semibold">{title}</h1>
      </div>

      <SuggestionStatusSummary
        createdAt={createdAt}
        expiresAt={expiresAt}
        status={status}
        suggestionId={suggestionId}
        updatedAt={updatedAt}
        version={version}
      />
    </div>
  );
}
