import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { useMyRuleSets } from "@/features/rules/hooks";
import {
  getSuggestionErrorMessage,
  useGenerateSuggestion,
  useSuggestionList,
} from "@/features/suggestions";
import { SuggestionList } from "@/features/suggestions/components/SuggestionList";
import type { SuggestionStatus, SuggestionStatusFilter } from "@/features/suggestions/types";
import { cn } from "@/shared/lib/utils";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppButton } from "@/shared/ui/app-button";
import { AppLoadingState } from "@/shared/ui/app-loading-state";
import { AppPageHeader } from "@/shared/ui/app-page-header";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { appActionRowClassName, appSelectControlClassName } from "@/shared/ui/design-tokens";
import { FieldHelpText } from "@/shared/ui/field-help-text";
import { InlineErrorText } from "@/shared/ui/inline-error-text";
import { Label } from "@/shared/ui/label";
import { Textarea } from "@/shared/ui/textarea";
import { toast } from "@/shared/ui/use-toast";

const promptSchema = z.string().trim().min(1).max(8000);
const promptTemplates = [
  {
    label: "Mask internal code",
    value:
      "Mask internal source code, repository paths, stack traces, and implementation details before the response is shown to end users.",
  },
  {
    label: "Block API key",
    value:
      "Block messages that contain API keys, access tokens, or other live credentials, especially if they look like production secrets.",
  },
  {
    label: "Mask email",
    value:
      "Mask email addresses when the conversation contains personal contact details that should not be exposed in plain text.",
  },
] as const;

const statusOptions: Array<{ label: string; value: SuggestionStatusFilter }> = [
  { label: "All", value: "all" },
  { label: "Draft", value: "draft" },
  { label: "Approved", value: "approved" },
  { label: "Applied", value: "applied" },
  { label: "Rejected", value: "rejected" },
  { label: "Expired", value: "expired" },
];
const limits = [20, 50, 100] as const;

export function SuggestionsPage() {
  const navigate = useNavigate();
  const myRuleSetsQuery = useMyRuleSets();
  const ruleSetId = myRuleSetsQuery.data?.[0]?.id;

  const [statusFilter, setStatusFilter] = useState<SuggestionStatusFilter>("all");
  const [limit, setLimit] = useState<number>(50);
  const [prompt, setPrompt] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);

  const listQuery = useSuggestionList(
    ruleSetId,
    statusFilter === "all" ? undefined : (statusFilter as SuggestionStatus),
    limit
  );
  const generateMutation = useGenerateSuggestion(ruleSetId);

  const sortedItems = useMemo(() => {
    const items = listQuery.data ?? [];
    return [...items].sort((a, b) => {
      const aTime = new Date(a.created_at).getTime();
      const bTime = new Date(b.created_at).getTime();
      return bTime - aTime;
    });
  }, [listQuery.data]);

  const handleGenerate = async () => {
    const parsed = promptSchema.safeParse(prompt);
    if (!parsed.success) {
      setValidationError("Prompt must be between 1 and 8000 characters.");
      setGenerateError(null);
      return;
    }

    setValidationError(null);
    setGenerateError(null);

    try {
      const generated = await generateMutation.mutateAsync({
        prompt: parsed.data,
      });
      toast({
        title: "Suggestion generated",
        description: "Review duplicate signal before continuing to draft.",
        variant: "success",
      });
      navigate(`/app/suggestions/${generated.id}`, {
        state: {
          initialStep: "generate",
          generationInsights: {
            suggestionId: generated.id,
            duplicate: generated.duplicate,
            duplicate_check: generated.duplicate_check,
          },
        },
      });
    } catch (error) {
      const message = getSuggestionErrorMessage(error, "Unable to generate suggestion");
      setGenerateError(message);
      toast({
        title: "Generate failed",
        description: message,
        variant: "destructive",
      });
    }
  };

  if (myRuleSetsQuery.isLoading) {
    return (
      <section className="p-6">
        <AppLoadingState
          className="mx-auto max-w-3xl"
          description="Loading the current rule set before showing suggestions."
          title="Loading suggestions"
        />
      </section>
    );
  }

  if (myRuleSetsQuery.isError || !ruleSetId) {
    return (
      <section className="p-6">
        <AppAlert title="Unable to resolve current rule set." variant="error" />
      </section>
    );
  }

  return (
    <section className="h-full overflow-auto p-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4">
        <AppPageHeader
          meta={`Rule set ID: ${ruleSetId}`}
          subtitle="Generate and manage the suggestion lifecycle for the current rule set."
          title="Rule Suggestions"
        />

        <AppSectionCard
          description="Describe the policy intent and create a new suggestion draft."
          title="Generate suggestion"
        >
          <div className="space-y-1.5">
            <Label htmlFor="suggestion-prompt" required>
              Suggestion prompt
            </Label>
            <Textarea
              id="suggestion-prompt"
              className="min-h-[120px]"
              onChange={(event) => {
                setPrompt(event.target.value);
                setGenerateError(null);
              }}
              placeholder="Example: Block messages that contain live API keys, bearer tokens, or production secrets copied from internal tools."
              value={prompt}
            />
            <FieldHelpText>Explain the user-facing policy goal first. Keep technical details secondary.</FieldHelpText>
          </div>
          <div className="space-y-2">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
              Quick templates
            </p>
            <div className="flex flex-wrap gap-2">
              {promptTemplates.map((template) => (
                <AppButton
                  key={template.label}
                  onClick={() => {
                    setPrompt(template.value);
                    setValidationError(null);
                    setGenerateError(null);
                  }}
                  size="sm"
                  type="button"
                  variant="secondary"
                >
                  {template.label}
                </AppButton>
              ))}
            </div>
          </div>
          {generateError ? (
            <AppAlert
              title="Cannot generate from this prompt yet"
              description={generateError}
              variant="error"
            />
          ) : null}
          {validationError ? <InlineErrorText>{validationError}</InlineErrorText> : null}
          <div className={appActionRowClassName}>
            <AppButton disabled={generateMutation.isPending} onClick={() => void handleGenerate()} type="button">
              {generateMutation.isPending ? "Generating..." : "Generate"}
            </AppButton>
          </div>
        </AppSectionCard>

        <AppSectionCard
          description="Browse recent suggestions with consistent filters for status and result count."
          title="Suggestion queue"
        >
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1">
              <Label htmlFor="suggestion-status-filter">Status</Label>
              <select
                className={cn(appSelectControlClassName, "h-9 min-w-[120px] w-auto py-0")}
                id="suggestion-status-filter"
                onChange={(event) => setStatusFilter(event.target.value as SuggestionStatusFilter)}
                value={statusFilter}
              >
                {statusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <Label htmlFor="suggestion-limit-filter">Limit</Label>
              <select
                className={cn(appSelectControlClassName, "h-9 min-w-[96px] w-auto py-0")}
                id="suggestion-limit-filter"
                onChange={(event) => setLimit(Number(event.target.value))}
                value={String(limit)}
              >
                {limits.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <SuggestionList
            errorMessage={getSuggestionErrorMessage(listQuery.error, "Unable to load suggestions")}
            isError={listQuery.isError}
            isLoading={listQuery.isLoading}
            items={sortedItems}
            onOpen={(id) => navigate(`/app/suggestions/${id}`)}
          />
        </AppSectionCard>
      </div>
    </section>
  );
}
