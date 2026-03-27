import { ArrowLeft } from "lucide-react";
import { StatusBadge } from "@/features/suggestions/components/StatusBadge";
import { SuggestionStatusSummary } from "@/features/suggestions/components/SuggestionStatusSummary";
import type { SuggestionStatus } from "@/features/suggestions/types";
import { AppButton } from "@/shared/ui/app-button";

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
    <div className="space-y-4">
      <AppButton
        leadingIcon={<ArrowLeft className="h-4 w-4" />}
        onClick={onBack}
        size="sm"
        type="button"
        variant="secondary"
      >
        Back
      </AppButton>

      <div className="space-y-3">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Rule suggestion</p>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-title font-semibold tracking-tight text-foreground">{title}</h1>
              <StatusBadge status={status} />
              <span className="rounded-full border border-border/70 bg-muted/60 px-2.5 py-1 text-xs font-medium text-muted-foreground">
                Version {version}
              </span>
            </div>
            <p className="text-sm text-muted-foreground">
              Review the current state and lifecycle dates before continuing through the workflow.
            </p>
          </div>
        </div>
      </div>

      <SuggestionStatusSummary
        createdAt={createdAt}
        expiresAt={expiresAt}
        suggestionId={suggestionId}
        updatedAt={updatedAt}
      />
    </div>
  );
}
