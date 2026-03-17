import { useEffect, useMemo, useState } from "react";
import { useMyRuleSets } from "@/features/rules/hooks";
import {
  useSystemPrompt,
  useUpdateSystemPrompt,
} from "@/features/settings/hooks";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { Textarea } from "@/shared/ui/textarea";
import { toast } from "@/shared/ui/use-toast";

const DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant.";

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

export function SystemPromptSettingsPage() {
  const myRuleSetsQuery = useMyRuleSets();
  const ruleSetId = myRuleSetsQuery.data?.[0]?.id;

  const systemPromptQuery = useSystemPrompt(ruleSetId);
  const updateMutation = useUpdateSystemPrompt(ruleSetId);

  const [draftPrompt, setDraftPrompt] = useState(DEFAULT_SYSTEM_PROMPT);
  const [savedPrompt, setSavedPrompt] = useState(DEFAULT_SYSTEM_PROMPT);

  useEffect(() => {
    const backendValue = systemPromptQuery.data?.system_prompt;
    const resolved = backendValue ?? DEFAULT_SYSTEM_PROMPT;
    setDraftPrompt(resolved);
    setSavedPrompt(resolved);
  }, [systemPromptQuery.data?.rule_set_id, systemPromptQuery.data?.system_prompt]);

  const isDirty = useMemo(() => draftPrompt !== savedPrompt, [draftPrompt, savedPrompt]);
  const characterCount = draftPrompt.length;

  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (!isDirty) {
        return;
      }
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);

  const handleSave = async () => {
    if (!ruleSetId) {
      return;
    }

    try {
      const updated = await updateMutation.mutateAsync({
        // Keep user formatting as-is; do not aggressive trim.
        system_prompt: draftPrompt,
      });
      const resolved = updated.system_prompt ?? DEFAULT_SYSTEM_PROMPT;
      setSavedPrompt(resolved);
      setDraftPrompt(resolved);
      toast({
        title: "System prompt updated",
        description: "Prompt settings have been saved.",
        variant: "success",
      });
    } catch (error) {
      toast({
        title: "Save failed",
        description: getErrorMessage(error, "Failed to update system prompt"),
        variant: "destructive",
      });
    }
  };

  const handleReset = () => {
    setDraftPrompt(DEFAULT_SYSTEM_PROMPT);
  };

  if (myRuleSetsQuery.isLoading || systemPromptQuery.isLoading) {
    return (
      <section className="h-full p-6">
        <Card className="p-4 text-sm text-muted-foreground">
          Loading system prompt...
        </Card>
      </section>
    );
  }

  if (myRuleSetsQuery.isError || !ruleSetId) {
    return (
      <section className="h-full p-6">
        <Card className="p-4 text-sm text-destructive">
          Unable to resolve current rule set.
        </Card>
      </section>
    );
  }

  if (systemPromptQuery.isError) {
    return (
      <section className="h-full p-6">
        <Card className="space-y-3 p-4 text-sm">
          <p className="text-destructive">
            {getErrorMessage(systemPromptQuery.error, "Failed to load system prompt")}
          </p>
          <Button
            onClick={() => {
              void systemPromptQuery.refetch();
            }}
            size="sm"
            type="button"
            variant="outline"
          >
            Retry
          </Button>
        </Card>
      </section>
    );
  }

  return (
    <section className="h-full overflow-auto p-6">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
        <header className="space-y-1">
          <h1 className="text-xl font-semibold">System Prompt</h1>
          <p className="text-sm text-muted-foreground">
            Configure assistant behavior for this rule set.
          </p>
          <p className="text-xs text-muted-foreground">Rule set ID: {ruleSetId}</p>
        </header>

        <Card className="space-y-3 p-4">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-medium">Prompt editor</p>
            <p className="text-xs text-muted-foreground">
              {characterCount} characters
            </p>
          </div>

          <Textarea
            className="min-h-[320px] whitespace-pre-wrap font-mono text-sm"
            onChange={(event) => setDraftPrompt(event.target.value)}
            placeholder={DEFAULT_SYSTEM_PROMPT}
            value={draftPrompt}
          />

          <div className="flex flex-wrap items-center justify-end gap-2">
            <Button
              onClick={handleReset}
              type="button"
              variant="outline"
            >
              Reset
            </Button>
            <Button
              disabled={!isDirty || updateMutation.isPending}
              onClick={() => {
                void handleSave();
              }}
              type="button"
            >
              {updateMutation.isPending ? "Saving..." : "Save"}
            </Button>
          </div>
        </Card>
      </div>
    </section>
  );
}

// Keep legacy name export to avoid touching router and other imports.
export const SystemPromptPage = SystemPromptSettingsPage;
