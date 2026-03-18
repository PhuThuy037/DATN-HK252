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
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { Textarea } from "@/shared/ui/textarea";
import { toast } from "@/shared/ui/use-toast";

const promptSchema = z.string().trim().min(1).max(8000);
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
      return;
    }

    setValidationError(null);

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
      toast({
        title: "Generate failed",
        description: getSuggestionErrorMessage(error, "Unable to generate suggestion"),
        variant: "destructive",
      });
    }
  };

  if (myRuleSetsQuery.isLoading) {
    return <section className="p-6 text-sm text-muted-foreground">Loading rule set...</section>;
  }

  if (myRuleSetsQuery.isError || !ruleSetId) {
    return (
      <section className="p-6">
        <Card className="p-4 text-sm text-destructive">Unable to resolve current rule set.</Card>
      </section>
    );
  }

  return (
    <section className="h-full overflow-auto p-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4">
        <header>
          <h1 className="text-xl font-semibold">Rule Suggestions</h1>
          <p className="text-sm text-muted-foreground">
            Generate and manage suggestion lifecycle for current rule set.
          </p>
        </header>

        <Card className="space-y-3 p-4">
          <p className="text-sm font-semibold">Generate suggestion</p>
          <Textarea
            className="min-h-[120px]"
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Describe policy intent to generate draft suggestion"
            value={prompt}
          />
          {validationError && <p className="text-xs text-destructive">{validationError}</p>}
          <div className="flex justify-end">
            <Button disabled={generateMutation.isPending} onClick={() => void handleGenerate()} type="button">
              {generateMutation.isPending ? "Generating..." : "Generate"}
            </Button>
          </div>
        </Card>

        <Card className="space-y-3 p-4">
          <div className="flex flex-wrap items-end gap-3">
            <label className="space-y-1 text-xs text-muted-foreground">
              <span className="block">Status</span>
              <select
                className="h-9 rounded-md border bg-background px-3 text-sm"
                onChange={(event) => setStatusFilter(event.target.value as SuggestionStatusFilter)}
                value={statusFilter}
              >
                {statusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1 text-xs text-muted-foreground">
              <span className="block">Limit</span>
              <select
                className="h-9 rounded-md border bg-background px-3 text-sm"
                onChange={(event) => setLimit(Number(event.target.value))}
                value={String(limit)}
              >
                {limits.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <SuggestionList
            errorMessage={getSuggestionErrorMessage(listQuery.error, "Unable to load suggestions")}
            isError={listQuery.isError}
            isLoading={listQuery.isLoading}
            items={sortedItems}
            onOpen={(id) => navigate(`/app/suggestions/${id}`)}
          />
        </Card>
      </div>
    </section>
  );
}
