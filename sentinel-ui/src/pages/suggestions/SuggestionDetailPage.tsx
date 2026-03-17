import { useEffect, useMemo, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { useMyRuleSets } from "@/features/rules/hooks";
import {
  SuggestionApiError,
  getSuggestionErrorMessage,
  useApplySuggestion,
  useConfirmSuggestion,
  useEditSuggestion,
  useRejectSuggestion,
  useSimulateSuggestion,
  useSuggestionDetail,
  useSuggestionLogs,
} from "@/features/suggestions";
import {
  DraftEditor,
  SimulatePanel,
  StatusBadge,
  SuggestionActions,
  SuggestionLogs,
  SuggestionStepper,
  canEditDraft,
  canSimulate,
  formatDate,
  type SuggestionStepKey,
} from "@/features/suggestions/components";
import type {
  RuleSuggestionGetOut,
  RuleSuggestionSimulateOut,
  SuggestionDraft,
} from "@/features/suggestions/types";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import { toast } from "@/shared/ui/use-toast";

function mapStatusToInitialStep(status: RuleSuggestionGetOut["status"]): SuggestionStepKey {
  if (status === "draft") {
    return "draft";
  }
  if (status === "approved") {
    return "decision";
  }
  if (status === "applied") {
    return "apply";
  }
  return "review";
}

function parseRuleJson(value: string) {
  const parsed = JSON.parse(value) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("draft.rule must be a JSON object");
  }
  return parsed as SuggestionDraft["rule"];
}

function parseContextTermsJson(value: string) {
  const parsed = JSON.parse(value) as unknown;
  if (!Array.isArray(parsed)) {
    throw new Error("draft.context_terms must be a JSON array");
  }
  return parsed as SuggestionDraft["context_terms"];
}

function isStaleVersionConflict(error: SuggestionApiError) {
  if (error.status !== 409) {
    return false;
  }

  return Boolean(
    error.details?.some(
      (detail) => detail.reason === "stale_version" || detail.field === "expected_version"
    )
  );
}

function validateDraft(rule: SuggestionDraft["rule"], contextTerms: SuggestionDraft["context_terms"]) {
  if (!rule.stable_key?.trim()) {
    return "stable_key is required";
  }
  if (!rule.name?.trim()) {
    return "name is required";
  }
  if (typeof rule.priority !== "number" || Number.isNaN(rule.priority)) {
    return "priority must be a valid number";
  }

  for (const term of contextTerms) {
    if (!term.entity_type?.trim() || !term.term?.trim()) {
      return "context_terms require entity_type and term";
    }
  }

  return null;
}

export function SuggestionDetailPage() {
  const navigate = useNavigate();
  const { suggestionId } = useParams();

  const myRuleSetsQuery = useMyRuleSets();
  const ruleSetId = myRuleSetsQuery.data?.[0]?.id;

  const detailQuery = useSuggestionDetail(ruleSetId, suggestionId);
  const logsQuery = useSuggestionLogs(ruleSetId, suggestionId, 100);

  const editMutation = useEditSuggestion(ruleSetId, suggestionId);
  const simulateMutation = useSimulateSuggestion(ruleSetId, suggestionId);
  const confirmMutation = useConfirmSuggestion(ruleSetId, suggestionId);
  const rejectMutation = useRejectSuggestion(ruleSetId, suggestionId);
  const applyMutation = useApplySuggestion(ruleSetId, suggestionId);

  const [activeStep, setActiveStep] = useState<SuggestionStepKey>("draft");
  const [sideTab, setSideTab] = useState<"simulate" | "logs" | "metadata">("simulate");
  const [ruleJson, setRuleJson] = useState("{}");
  const [contextTermsJson, setContextTermsJson] = useState("[]");
  const [draftValidationError, setDraftValidationError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [staleBanner, setStaleBanner] = useState<string | null>(null);
  const [unsavedDraftSnapshot, setUnsavedDraftSnapshot] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [simulateResult, setSimulateResult] = useState<RuleSuggestionSimulateOut | null>(null);
  const [simulateError, setSimulateError] = useState<string | null>(null);

  useEffect(() => {
    if (!detailQuery.data) {
      return;
    }
    setRuleJson(JSON.stringify(detailQuery.data.draft.rule, null, 2));
    setContextTermsJson(JSON.stringify(detailQuery.data.draft.context_terms, null, 2));
    setActiveStep(mapStatusToInitialStep(detailQuery.data.status));
    setDraftValidationError(null);
    setActionError(null);
    setStaleBanner(null);
  }, [detailQuery.data?.id, detailQuery.data?.version]);

  const hasDirtyDraft = useMemo(() => {
    if (!detailQuery.data) {
      return false;
    }
    const serverRuleJson = JSON.stringify(detailQuery.data.draft.rule, null, 2).trim();
    const serverTermsJson = JSON.stringify(detailQuery.data.draft.context_terms, null, 2).trim();
    return ruleJson.trim() !== serverRuleJson || contextTermsJson.trim() !== serverTermsJson;
  }, [contextTermsJson, detailQuery.data, ruleJson]);

  const handleStaleConflict = async (message: string) => {
    setStaleBanner(message);
    setUnsavedDraftSnapshot(
      JSON.stringify(
        {
          rule: parseSafeJson(ruleJson),
          context_terms: parseSafeJson(contextTermsJson),
        },
        null,
        2
      )
    );
    await detailQuery.refetch();
  };

  const handleSaveDraft = async () => {
    if (!detailQuery.data) {
      return;
    }

    setDraftValidationError(null);
    setActionError(null);
    setStaleBanner(null);

    let nextRule: SuggestionDraft["rule"];
    let nextTerms: SuggestionDraft["context_terms"];

    try {
      nextRule = parseRuleJson(ruleJson);
      nextTerms = parseContextTermsJson(contextTermsJson);
    } catch (error) {
      setDraftValidationError(
        error instanceof Error ? error.message : "Invalid draft JSON format"
      );
      return;
    }

    const validationMessage = validateDraft(nextRule, nextTerms);
    if (validationMessage) {
      setDraftValidationError(validationMessage);
      return;
    }

    try {
      const saved = await editMutation.mutateAsync({
        draft: {
          rule: nextRule,
          context_terms: nextTerms,
        },
        expected_version: detailQuery.data.version,
      });

      setRuleJson(JSON.stringify(saved.draft.rule, null, 2));
      setContextTermsJson(JSON.stringify(saved.draft.context_terms, null, 2));
      toast({
        title: "Draft saved",
        description: "Suggestion draft has been updated.",
        variant: "success",
      });
    } catch (error) {
      if (error instanceof SuggestionApiError && isStaleVersionConflict(error)) {
        await handleStaleConflict("Draft dã b? thay d?i ? noi khác. Vui lòng t?i l?i d? li?u m?i nh?t.");
        return;
      }
      setActionError(getSuggestionErrorMessage(error, "Failed to save draft"));
    }
  };

  const handleConfirm = async () => {
    if (!detailQuery.data) {
      return;
    }

    setActionError(null);
    setStaleBanner(null);

    try {
      await confirmMutation.mutateAsync({
        expected_version: detailQuery.data.version,
      });
      await detailQuery.refetch();
      toast({
        title: "Suggestion approved",
        description: "Status changed to approved.",
        variant: "success",
      });
    } catch (error) {
      if (error instanceof SuggestionApiError && isStaleVersionConflict(error)) {
        await handleStaleConflict("Draft dã b? thay d?i ? noi khác. Vui lòng t?i l?i d? li?u m?i nh?t.");
        return;
      }
      setActionError(getSuggestionErrorMessage(error, "Failed to confirm suggestion"));
    }
  };

  const handleReject = async (reason?: string | null) => {
    if (!detailQuery.data) {
      return;
    }

    setActionError(null);
    setStaleBanner(null);

    try {
      await rejectMutation.mutateAsync({
        reason,
        expected_version: detailQuery.data.version,
      });
      await detailQuery.refetch();
      toast({
        title: "Suggestion rejected",
        description: "Status changed to rejected.",
        variant: "success",
      });
    } catch (error) {
      if (error instanceof SuggestionApiError && isStaleVersionConflict(error)) {
        await handleStaleConflict("Draft dã b? thay d?i ? noi khác. Vui lòng t?i l?i d? li?u m?i nh?t.");
        return;
      }
      setActionError(getSuggestionErrorMessage(error, "Failed to reject suggestion"));
    }
  };

  const handleApply = async () => {
    if (!detailQuery.data) {
      return;
    }

    setActionError(null);
    setStaleBanner(null);

    try {
      const applied = await applyMutation.mutateAsync({
        expected_version: detailQuery.data.version,
      });
      await detailQuery.refetch();
      toast({
        title: "Suggestion applied",
        description: `Rule ${applied.stable_key} has been applied.`,
        variant: "success",
      });
    } catch (error) {
      if (error instanceof SuggestionApiError && isStaleVersionConflict(error)) {
        await handleStaleConflict("Draft dã b? thay d?i ? noi khác. Vui lòng t?i l?i d? li?u m?i nh?t.");
        return;
      }
      setActionError(getSuggestionErrorMessage(error, "Failed to apply suggestion"));
    }
  };

  const handleSimulate = async (payload: { samples: string[]; include_examples: boolean }) => {
    setSimulateError(null);

    try {
      const result = await simulateMutation.mutateAsync(payload);
      setSimulateResult(result);
      setSideTab("simulate");
    } catch (error) {
      setSimulateError(getSuggestionErrorMessage(error, "Failed to simulate suggestion"));
    }
  };

  if (myRuleSetsQuery.isLoading || detailQuery.isLoading) {
    return <section className="p-6 text-sm text-muted-foreground">Loading suggestion detail...</section>;
  }

  if (myRuleSetsQuery.isError || !ruleSetId) {
    return (
      <section className="p-6">
        <Card className="p-4 text-sm text-destructive">Unable to resolve current rule set.</Card>
      </section>
    );
  }

  if (detailQuery.isError || !detailQuery.data) {
    const status = detailQuery.error instanceof SuggestionApiError ? detailQuery.error.status : undefined;

    if (status === 403) {
      return (
        <section className="p-6">
          <Card className="p-4 text-sm text-destructive">You do not have permission to view this suggestion.</Card>
        </section>
      );
    }

    if (status === 404) {
      return (
        <section className="p-6">
          <Card className="p-4 text-sm">Suggestion not found.</Card>
        </section>
      );
    }

    return (
      <section className="p-6">
        <Card className="p-4 text-sm text-destructive">
          {getSuggestionErrorMessage(detailQuery.error, "Failed to load suggestion detail")}
        </Card>
      </section>
    );
  }

  const suggestion = detailQuery.data;

  return (
    <section className="h-full overflow-auto p-6">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4">
        <div className="flex items-center justify-between gap-3">
          <Button onClick={() => navigate("/app/suggestions")} size="sm" type="button" variant="outline">
            <ArrowLeft className="mr-1 h-4 w-4" />
            Back
          </Button>

          <SuggestionActions
            hasDirtyDraft={hasDirtyDraft}
            isApplying={applyMutation.isPending}
            isConfirming={confirmMutation.isPending}
            isRejecting={rejectMutation.isPending}
            isSaving={editMutation.isPending}
            onApply={handleApply}
            onConfirm={handleConfirm}
            onOpenSimulate={() => {
              setActiveStep("simulate");
              setSideTab("simulate");
            }}
            onReject={async (reason) => {
              setRejectReason(reason ?? "");
              await handleReject(reason);
            }}
            onSaveDraft={handleSaveDraft}
            status={suggestion.status}
          />
        </div>

        <Card className="space-y-2 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={suggestion.status} />
            <span className="text-xs text-muted-foreground">v{suggestion.version}</span>
            <span className="text-xs text-muted-foreground">ID: {suggestion.id}</span>
          </div>
          <div className="grid gap-1 text-xs text-muted-foreground md:grid-cols-2">
            <p>created_at: {formatDate(suggestion.created_at)}</p>
            <p>updated_at: {formatDate(suggestion.updated_at)}</p>
            <p>expires_at: {formatDate(suggestion.expires_at)}</p>
            <p>type: {suggestion.type}</p>
          </div>
          <div className="rounded-md border bg-muted/30 p-3">
            <p className="text-xs font-medium text-muted-foreground">nl_input</p>
            <p className="mt-1 text-sm">{suggestion.nl_input}</p>
          </div>
        </Card>

        {staleBanner && (
          <Card className="border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">{staleBanner}</Card>
        )}

        {actionError && (
          <Card className="border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{actionError}</Card>
        )}

        <div className="grid h-full min-h-0 gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="space-y-4 min-h-0">
            <SuggestionStepper activeStep={activeStep} onStepChange={setActiveStep} status={suggestion.status} />

            {activeStep === "generate" && (
              <Card className="p-4">
                <p className="text-sm font-semibold">Generate step</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Suggestion was generated from your natural language prompt. You can move to Draft or Simulate anytime.
                </p>
              </Card>
            )}

            {activeStep === "draft" && (
              <Card className="p-4">
                <DraftEditor
                  contextTermsJson={contextTermsJson}
                  onContextTermsJsonChange={setContextTermsJson}
                  onRuleJsonChange={setRuleJson}
                  readOnly={!canEditDraft(suggestion.status)}
                  ruleJson={ruleJson}
                  validationError={draftValidationError}
                />
              </Card>
            )}

            {activeStep === "simulate" && (
              <SimulatePanel
                disabled={!canSimulate(suggestion.status)}
                errorMessage={simulateError}
                isSubmitting={simulateMutation.isPending}
                onSimulate={handleSimulate}
                result={simulateResult}
              />
            )}

            {activeStep === "review" && (
              <Card className="space-y-3 p-4">
                <p className="text-sm font-semibold">Review</p>
                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">explanation</p>
                  <pre className="overflow-auto rounded-md bg-muted p-3 text-xs">
                    {JSON.stringify(suggestion.explanation, null, 2)}
                  </pre>
                </div>
                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">quality_signals</p>
                  <pre className="overflow-auto rounded-md bg-muted p-3 text-xs">
                    {JSON.stringify(suggestion.quality_signals, null, 2)}
                  </pre>
                </div>
              </Card>
            )}

            {activeStep === "decision" && (
              <Card className="p-4 text-sm text-muted-foreground">
                <p>Current status: {suggestion.status}</p>
                <p className="mt-1">Use action bar to confirm or reject based on your review.</p>
                {rejectReason && <p className="mt-1 text-xs">Last reject reason input: {rejectReason}</p>}
              </Card>
            )}

            {activeStep === "apply" && (
              <Card className="space-y-3 p-4">
                <p className="text-sm font-semibold">Apply result</p>
                {suggestion.applied_result_json ? (
                  <pre className="overflow-auto rounded-md bg-muted p-3 text-xs">
                    {JSON.stringify(suggestion.applied_result_json, null, 2)}
                  </pre>
                ) : (
                  <p className="text-sm text-muted-foreground">No applied_result_json available yet.</p>
                )}
              </Card>
            )}

            {unsavedDraftSnapshot && (
              <details className="rounded-md border p-3 text-xs">
                <summary className="cursor-pointer font-medium text-muted-foreground">
                  Unsaved local draft snapshot (for manual copy)
                </summary>
                <pre className="mt-2 overflow-auto rounded-md bg-muted p-3 text-[11px]">{unsavedDraftSnapshot}</pre>
              </details>
            )}
          </div>

          <div className="min-h-0">
            <Tabs className="h-full" onValueChange={(value) => setSideTab(value as typeof sideTab)} value={sideTab}>
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="simulate">Simulate</TabsTrigger>
                <TabsTrigger value="logs">Logs</TabsTrigger>
                <TabsTrigger value="metadata">Metadata</TabsTrigger>
              </TabsList>

              <TabsContent className="mt-3" value="simulate">
                <SimulatePanel
                  disabled={!canSimulate(suggestion.status)}
                  errorMessage={simulateError}
                  isSubmitting={simulateMutation.isPending}
                  onSimulate={handleSimulate}
                  result={simulateResult}
                />
              </TabsContent>

              <TabsContent className="mt-3" value="logs">
                <SuggestionLogs
                  errorMessage={getSuggestionErrorMessage(logsQuery.error, "Failed to load logs")}
                  isError={logsQuery.isError}
                  isLoading={logsQuery.isLoading}
                  logs={logsQuery.data ?? []}
                />
              </TabsContent>

              <TabsContent className="mt-3" value="metadata">
                <Card className="space-y-3 p-4">
                  <p className="text-sm font-semibold">Metadata</p>
                  <div className="space-y-1 text-xs text-muted-foreground">
                    <p>dedupe_key: {suggestion.dedupe_key}</p>
                    <p>created_by: {suggestion.created_by}</p>
                    <p>type: {suggestion.type}</p>
                    <p>status: {suggestion.status}</p>
                  </div>
                  <details className="rounded-md border p-2 text-xs">
                    <summary className="cursor-pointer font-medium text-muted-foreground">draft</summary>
                    <pre className="mt-2 overflow-auto rounded-md bg-muted p-2 text-[11px]">
                      {JSON.stringify(suggestion.draft, null, 2)}
                    </pre>
                  </details>
                  {suggestion.applied_result_json && (
                    <details className="rounded-md border p-2 text-xs" open>
                      <summary className="cursor-pointer font-medium text-muted-foreground">applied_result_json</summary>
                      <pre className="mt-2 overflow-auto rounded-md bg-muted p-2 text-[11px]">
                        {JSON.stringify(suggestion.applied_result_json, null, 2)}
                      </pre>
                    </details>
                  )}
                </Card>
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </div>
    </section>
  );
}

function parseSafeJson(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}
