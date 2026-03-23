import { useEffect, useMemo, useRef, useState } from "react";
import { Navigate, useLocation, useNavigate, useParams } from "react-router-dom";
import { getRuleDetail } from "@/features/rules";
import type { RuleDetail } from "@/features/rules/types";
import { useRuleSetStore } from "@/features/rules/store/ruleSetStore";
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
  SuggestionActionDialog,
  SuggestionApplyStep,
  SuggestionDecisionStep,
  SuggestionDraftStep,
  SuggestionGenerateStep,
  SuggestionHeader,
  SuggestionRuleInspectorDialog,
  SuggestionReviewStep,
  SuggestionSimulateStep,
  SuggestionStepper,
  SuggestionTechnicalDetails,
  type SuggestionStepKey,
} from "@/features/suggestions/components";
import type {
  RuleSuggestionGetOut,
  RuleSuggestionSimulateOut,
  SuggestionDraft,
  SuggestionDuplicate,
  SuggestionDuplicateCandidate,
  SuggestionDuplicateCheck,
} from "@/features/suggestions/types";
import { canEditDraft } from "@/features/suggestions/components/StatusBadge";
import { Card } from "@/shared/ui/card";
import { Textarea } from "@/shared/ui/textarea";
import { toast } from "@/shared/ui/use-toast";

type SuggestionDetailLocationState = {
  initialStep?: SuggestionStepKey;
  generationInsights?: {
    suggestionId: string;
    duplicate?: SuggestionDuplicate;
    duplicate_check?: SuggestionDuplicateCheck;
  };
};

type DuplicateInsight = {
  level?: "none" | "weak" | "strong";
  reason?: string;
  duplicateRisk?: string;
  conflictRisk?: string;
  runtimeUsable?: boolean;
  rationale?: string;
  similarRules?: SuggestionDuplicateCandidate[];
  candidates?: SuggestionDuplicateCandidate[];
};

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
    return "Stable key is required";
  }
  if (!rule.name?.trim()) {
    return "Name is required";
  }
  if (typeof rule.priority !== "number" || Number.isNaN(rule.priority)) {
    return "Priority must be a valid number";
  }

  for (const term of contextTerms) {
    if (!term.entity_type?.trim() || !term.term?.trim()) {
      return "Each context term requires entity_type and term";
    }
  }

  return null;
}

function cloneDraft(value: SuggestionDraft): SuggestionDraft {
  return JSON.parse(JSON.stringify(value)) as SuggestionDraft;
}

function buildHeaderTitle(value: string) {
  const trimmed = value.trim();
  if (trimmed.length <= 80) {
    return trimmed;
  }
  return `${trimmed.slice(0, 80)}...`;
}

function getRuleDetailErrorMessage(error: unknown) {
  const serverMessage =
    typeof error === "object" &&
    error !== null &&
    "response" in error &&
    typeof (error as { response?: unknown }).response === "object" &&
    (error as { response?: { data?: { error?: { message?: unknown } } } }).response?.data?.error
      ?.message;

  if (typeof serverMessage === "string" && serverMessage.trim().length > 0) {
    return serverMessage;
  }
  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }
  return "Failed to load rule detail";
}

function asDuplicateCandidates(value: unknown): SuggestionDuplicateCandidate[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }
      const record = item as Record<string, unknown>;
      return {
        rule_id: String(record.rule_id ?? ""),
        stable_key: String(record.stable_key ?? ""),
        name: String(record.name ?? ""),
        origin: String(record.origin ?? ""),
        similarity: Number(record.similarity ?? record.score ?? 0),
        lexical_score: Number(record.lexical_score ?? 0),
        action: record.action ? String(record.action) : null,
        scope: record.scope ? String(record.scope) : null,
        summary: record.summary
          ? String(record.summary)
          : record.description
            ? String(record.description)
            : null,
      } as SuggestionDuplicateCandidate;
    })
    .filter((candidate): candidate is SuggestionDuplicateCandidate => Boolean(candidate?.rule_id));
}

function normalizeDuplicateLevel(
  rawLevel: unknown,
  decision: string | undefined,
  similarRuleCount: number
): "none" | "weak" | "strong" {
  const levelText = typeof rawLevel === "string" ? rawLevel.trim().toLowerCase() : "";
  if (levelText === "strong" || levelText === "weak" || levelText === "none") {
    return levelText;
  }
  if (similarRuleCount > 0) {
    return "strong";
  }
  if (decision && decision.toUpperCase() !== "DIFFERENT") {
    return "weak";
  }
  return "none";
}

function extractDuplicateFromUnknown(value: unknown): DuplicateInsight | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const record = value as Record<string, unknown>;
  const decision = typeof record.decision === "string" ? record.decision : undefined;
  const similarRules = asDuplicateCandidates(record.similar_rules ?? record.candidates);
  const level = normalizeDuplicateLevel(record.level, decision, similarRules.length);
  const reason =
    typeof record.reason === "string"
      ? record.reason
      : typeof record.rationale === "string"
        ? record.rationale
        : undefined;

  return {
    level,
    reason,
    duplicateRisk: decision,
    rationale: reason,
    similarRules,
    candidates: similarRules,
  };
}

function extractDuplicateInsight(
  suggestion: RuleSuggestionGetOut,
  logs: Array<{ before_json?: Record<string, unknown> | null; after_json?: Record<string, unknown> | null }> | undefined,
  locationState: SuggestionDetailLocationState | null
): DuplicateInsight {
  const base: DuplicateInsight = {
    level: "none",
    duplicateRisk: suggestion.quality_signals?.duplicate_risk,
    conflictRisk: suggestion.quality_signals?.conflict_risk,
    runtimeUsable: suggestion.quality_signals?.runtime_usable,
    similarRules: [],
    candidates: [],
  };

  if (
    locationState?.generationInsights?.suggestionId === suggestion.id &&
    locationState.generationInsights.duplicate
  ) {
    const fromLocationDuplicate = extractDuplicateFromUnknown(
      locationState.generationInsights.duplicate
    );
    if (fromLocationDuplicate) {
      return {
        ...base,
        ...fromLocationDuplicate,
      };
    }
  }

  if (
    locationState?.generationInsights?.suggestionId === suggestion.id &&
    locationState.generationInsights.duplicate_check
  ) {
    const fromLocationLegacy = extractDuplicateFromUnknown(
      locationState.generationInsights.duplicate_check
    );
    if (fromLocationLegacy) {
      return {
        ...base,
        ...fromLocationLegacy,
      };
    }
  }

  const fromSuggestion = extractDuplicateFromUnknown(suggestion.duplicate);
  if (fromSuggestion) {
    return {
      ...base,
      ...fromSuggestion,
    };
  }

  if (Array.isArray(logs)) {
    for (const log of logs) {
      const fromAfter = extractDuplicateFromUnknown(log.after_json?.duplicate);
      if (fromAfter) {
        return {
          ...base,
          ...fromAfter,
        };
      }

      const fromAfterLegacy = extractDuplicateFromUnknown(log.after_json?.duplicate_check);
      if (fromAfterLegacy) {
        return {
          ...base,
          ...fromAfterLegacy,
        };
      }

      const fromBefore = extractDuplicateFromUnknown(log.before_json?.duplicate);
      if (fromBefore) {
        return {
          ...base,
          ...fromBefore,
        };
      }

      const fromBeforeLegacy = extractDuplicateFromUnknown(log.before_json?.duplicate_check);
      if (fromBeforeLegacy) {
        return {
          ...base,
          ...fromBeforeLegacy,
        };
      }
    }
  }

  return base;
}

export function SuggestionDetailPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { suggestionId } = useParams();

  const locationState = (location.state as SuggestionDetailLocationState | null) ?? null;

  const currentRuleSetId = useRuleSetStore((state) => state.currentRuleSetId);
  const isRuleSetResolved = useRuleSetStore((state) => state.isRuleSetResolved);

  const detailQuery = useSuggestionDetail(currentRuleSetId ?? undefined, suggestionId);
  const logsQuery = useSuggestionLogs(currentRuleSetId ?? undefined, suggestionId, 100);

  const editMutation = useEditSuggestion(currentRuleSetId ?? undefined, suggestionId);
  const simulateMutation = useSimulateSuggestion(currentRuleSetId ?? undefined, suggestionId);
  const confirmMutation = useConfirmSuggestion(currentRuleSetId ?? undefined, suggestionId);
  const rejectMutation = useRejectSuggestion(currentRuleSetId ?? undefined, suggestionId);
  const applyMutation = useApplySuggestion(currentRuleSetId ?? undefined, suggestionId);

  const [activeStep, setActiveStep] = useState<SuggestionStepKey>("draft");
  const [draftState, setDraftState] = useState<SuggestionDraft | null>(null);
  const [draftValidationError, setDraftValidationError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [staleBanner, setStaleBanner] = useState<string | null>(null);
  const [unsavedDraftSnapshot, setUnsavedDraftSnapshot] = useState<string | null>(null);

  const [simulateResult, setSimulateResult] = useState<RuleSuggestionSimulateOut | null>(null);
  const [simulateError, setSimulateError] = useState<string | null>(null);

  const [isConfirmDialogOpen, setIsConfirmDialogOpen] = useState(false);
  const [isRejectDialogOpen, setIsRejectDialogOpen] = useState(false);
  const [isApplyDialogOpen, setIsApplyDialogOpen] = useState(false);
  const [isRuleInspectorOpen, setIsRuleInspectorOpen] = useState(false);
  const [ruleInspectorMode, setRuleInspectorMode] = useState<"view" | "compare">("view");
  const [selectedDuplicateCandidate, setSelectedDuplicateCandidate] =
    useState<SuggestionDuplicateCandidate | null>(null);
  const [selectedRuleDetail, setSelectedRuleDetail] = useState<RuleDetail | null>(null);
  const [ruleInspectorError, setRuleInspectorError] = useState<string | null>(null);
  const [isRuleInspectorLoading, setIsRuleInspectorLoading] = useState(false);
  const [rejectReasonInput, setRejectReasonInput] = useState("");
  const initializedSuggestionIdRef = useRef<string | null>(null);
  const ruleInspectorRequestIdRef = useRef(0);

  useEffect(() => {
    if (!detailQuery.data) {
      return;
    }

    setDraftState(cloneDraft(detailQuery.data.draft));

    const isNewSuggestion = initializedSuggestionIdRef.current !== detailQuery.data.id;
    if (isNewSuggestion) {
      initializedSuggestionIdRef.current = detailQuery.data.id;

      const shouldStartAtGenerate =
        locationState?.initialStep === "generate" &&
        locationState?.generationInsights?.suggestionId === detailQuery.data.id;

      setActiveStep(
        shouldStartAtGenerate ? "generate" : mapStatusToInitialStep(detailQuery.data.status)
      );

      if (shouldStartAtGenerate) {
        navigate(location.pathname, { replace: true });
      }
    }

    setDraftValidationError(null);
    setActionError(null);
    setStaleBanner(null);
  }, [
    detailQuery.data?.id,
    detailQuery.data?.version,
    location.pathname,
    locationState?.generationInsights?.suggestionId,
    locationState?.initialStep,
    navigate,
  ]);

  const hasDirtyDraft = useMemo(() => {
    if (!detailQuery.data || !draftState) {
      return false;
    }

    return JSON.stringify(draftState) !== JSON.stringify(detailQuery.data.draft);
  }, [detailQuery.data, draftState]);

  const duplicateInsight = useMemo(() => {
    if (!detailQuery.data) {
      return null;
    }

    return extractDuplicateInsight(detailQuery.data, logsQuery.data, locationState);
  }, [detailQuery.data, locationState, logsQuery.data]);

  const handleStaleConflict = async (message: string) => {
    setStaleBanner(message);
    setUnsavedDraftSnapshot(draftState ? JSON.stringify(draftState, null, 2) : null);
    await detailQuery.refetch();
  };

  const handleSaveDraft = async () => {
    if (!detailQuery.data || !draftState || !canEditDraft(detailQuery.data.status)) {
      return;
    }

    setDraftValidationError(null);
    setActionError(null);
    setStaleBanner(null);

    const validationMessage = validateDraft(draftState.rule, draftState.context_terms);
    if (validationMessage) {
      setDraftValidationError(validationMessage);
      return;
    }

    try {
      const saved = await editMutation.mutateAsync({
        draft: draftState,
        expected_version: detailQuery.data.version,
      });

      setDraftState(cloneDraft(saved.draft));
      await detailQuery.refetch();

      toast({
        title: "Draft saved",
        description: "Suggestion draft has been updated.",
        variant: "success",
      });
    } catch (error) {
      if (error instanceof SuggestionApiError && isStaleVersionConflict(error)) {
        await handleStaleConflict(
          "Suggestion was updated elsewhere. Please review the latest data and apply your changes again."
        );
        return;
      }
      const message = getSuggestionErrorMessage(error, "Failed to save draft");
      setActionError(message);
      toast({
        title: "Save draft failed",
        description: message,
        variant: "destructive",
      });
    }
  };

  const handleConfirm = async () => {
    if (!detailQuery.data) {
      return;
    }

    setActionError(null);
    setStaleBanner(null);

    try {
      await confirmMutation.mutateAsync({ expected_version: detailQuery.data.version });
      await detailQuery.refetch();
      setIsConfirmDialogOpen(false);
      toast({
        title: "Suggestion confirmed",
        description: "Status is now approved.",
        variant: "success",
      });
    } catch (error) {
      if (error instanceof SuggestionApiError && isStaleVersionConflict(error)) {
        await handleStaleConflict(
          "Suggestion was updated elsewhere. Please review the latest data and apply your changes again."
        );
        return;
      }
      const message = getSuggestionErrorMessage(error, "Failed to confirm suggestion");
      setActionError(message);
      toast({
        title: "Confirm failed",
        description: message,
        variant: "destructive",
      });
    }
  };

  const handleReject = async () => {
    if (!detailQuery.data) {
      return;
    }

    setActionError(null);
    setStaleBanner(null);

    try {
      await rejectMutation.mutateAsync({
        reason: rejectReasonInput.trim() || null,
        expected_version: detailQuery.data.version,
      });
      await detailQuery.refetch();
      setIsRejectDialogOpen(false);
      setRejectReasonInput("");
      toast({
        title: "Suggestion rejected",
        description: "Status is now rejected.",
        variant: "success",
      });
    } catch (error) {
      if (error instanceof SuggestionApiError && isStaleVersionConflict(error)) {
        await handleStaleConflict(
          "Suggestion was updated elsewhere. Please review the latest data and apply your changes again."
        );
        return;
      }
      const message = getSuggestionErrorMessage(error, "Failed to reject suggestion");
      setActionError(message);
      toast({
        title: "Reject failed",
        description: message,
        variant: "destructive",
      });
    }
  };

  const handleApply = async () => {
    if (!detailQuery.data) {
      return;
    }

    setActionError(null);
    setStaleBanner(null);

    try {
      const applied = await applyMutation.mutateAsync({ expected_version: detailQuery.data.version });
      await detailQuery.refetch();
      setIsApplyDialogOpen(false);
      toast({
        title: "Suggestion applied",
        description: `Rule ${applied.stable_key} has been applied.`,
        variant: "success",
      });
    } catch (error) {
      if (error instanceof SuggestionApiError && isStaleVersionConflict(error)) {
        await handleStaleConflict(
          "Suggestion was updated elsewhere. Please review the latest data and apply your changes again."
        );
        return;
      }
      const message = getSuggestionErrorMessage(error, "Failed to apply suggestion");
      setActionError(message);
      toast({
        title: "Apply failed",
        description: message,
        variant: "destructive",
      });
    }
  };

  const handleSimulate = async (payload: { samples: string[]; include_examples: boolean }) => {
    setSimulateError(null);

    try {
      const result = await simulateMutation.mutateAsync(payload);
      setSimulateResult(result);
      toast({
        title: "Simulation complete",
        description: `Processed ${result.sample_size} samples.`,
        variant: "success",
      });
    } catch (error) {
      const message = getSuggestionErrorMessage(error, "Failed to simulate suggestion");
      setSimulateError(message);
      toast({
        title: "Simulation failed",
        description: message,
        variant: "destructive",
      });
    }
  };

  const handleContinueToDraft = () => {
    setActiveStep("draft");
  };

  const loadRuleDetailByCandidate = async (candidate: SuggestionDuplicateCandidate) => {
    const requestId = ruleInspectorRequestIdRef.current + 1;
    ruleInspectorRequestIdRef.current = requestId;
    setSelectedRuleDetail(null);
    setRuleInspectorError(null);
    setIsRuleInspectorLoading(true);

    try {
      const ruleDetail = await getRuleDetail(candidate.rule_id);
      if (ruleInspectorRequestIdRef.current !== requestId) {
        return;
      }
      setSelectedRuleDetail(ruleDetail);
    } catch (error) {
      if (ruleInspectorRequestIdRef.current !== requestId) {
        return;
      }
      setRuleInspectorError(getRuleDetailErrorMessage(error));
    } finally {
      if (ruleInspectorRequestIdRef.current === requestId) {
        setIsRuleInspectorLoading(false);
      }
    }
  };

  const openRuleInspector = (
    mode: "view" | "compare",
    candidate: SuggestionDuplicateCandidate
  ) => {
    setRuleInspectorMode(mode);
    setSelectedDuplicateCandidate(candidate);
    setIsRuleInspectorOpen(true);
    void loadRuleDetailByCandidate(candidate);
  };

  const handleViewDuplicateRule = (candidate: SuggestionDuplicateCandidate) => {
    openRuleInspector("view", candidate);
  };

  const handleCompareDuplicateRule = (candidate: SuggestionDuplicateCandidate) => {
    openRuleInspector("compare", candidate);
  };

  const handleRetryLoadRuleDetail = () => {
    if (!selectedDuplicateCandidate) {
      return;
    }
    void loadRuleDetailByCandidate(selectedDuplicateCandidate);
  };

  const handleCloseRuleInspector = () => {
    ruleInspectorRequestIdRef.current += 1;
    setIsRuleInspectorOpen(false);
    setIsRuleInspectorLoading(false);
    setRuleInspectorError(null);
  };

  const handleEditExistingRule = () => {
    if (!selectedDuplicateCandidate) {
      return;
    }

    const ruleId = encodeURIComponent(selectedDuplicateCandidate.rule_id);
    handleCloseRuleInspector();
    navigate(`/app/settings/rules?editRuleId=${ruleId}&source=suggestion-compare`);
  };

  const handleContinueAnywayFromCompare = () => {
    handleCloseRuleInspector();
    setActiveStep("draft");
  };

  if (!isRuleSetResolved) {
    return <section className="p-6 text-sm text-muted-foreground">Resolving workspace...</section>;
  }

  if (!currentRuleSetId) {
    return <Navigate replace to="/onboarding/rule-set" />;
  }

  if (detailQuery.isLoading) {
    return <section className="p-6 text-sm text-muted-foreground">Loading suggestion detail...</section>;
  }

  if (detailQuery.isError || !detailQuery.data) {
    const status = detailQuery.error instanceof SuggestionApiError ? detailQuery.error.status : undefined;

    if (status === 403) {
      return (
        <section className="p-6">
          <Card className="p-4 text-sm text-destructive">
            You do not have permission to view this suggestion.
          </Card>
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
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4">
        <Card className="p-4">
          <SuggestionHeader
            createdAt={suggestion.created_at}
            expiresAt={suggestion.expires_at}
            onBack={() => navigate("/app/suggestions")}
            status={suggestion.status}
            suggestionId={suggestion.id}
            title={buildHeaderTitle(suggestion.nl_input)}
            updatedAt={suggestion.updated_at}
            version={suggestion.version}
          />
        </Card>

        {staleBanner && (
          <Card className="border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">{staleBanner}</Card>
        )}

        {actionError && (
          <Card className="border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {actionError}
          </Card>
        )}

        <SuggestionStepper activeStep={activeStep} onStepChange={setActiveStep} status={suggestion.status} />

        {activeStep === "generate" && (
          <SuggestionGenerateStep
            duplicateInsight={duplicateInsight}
            onCompareDuplicateRule={handleCompareDuplicateRule}
            onContinueToDraft={handleContinueToDraft}
            onViewDuplicateRule={handleViewDuplicateRule}
            prompt={suggestion.nl_input}
          />
        )}

        {activeStep === "draft" && draftState && (
          <SuggestionDraftStep
            draft={draftState}
            hasDirtyDraft={hasDirtyDraft}
            isSaving={editMutation.isPending}
            onDraftChange={setDraftState}
            onSaveDraft={() => void handleSaveDraft()}
            status={suggestion.status}
            validationError={draftValidationError}
          />
        )}

        {activeStep === "simulate" && (
          <SuggestionSimulateStep
            errorMessage={simulateError}
            isSubmitting={simulateMutation.isPending}
            onSimulate={handleSimulate}
            result={simulateResult}
            status={suggestion.status}
          />
        )}

        {activeStep === "review" && <SuggestionReviewStep suggestion={suggestion} />}

        {activeStep === "decision" && (
          <SuggestionDecisionStep
            isConfirming={confirmMutation.isPending}
            isRejecting={rejectMutation.isPending}
            onOpenConfirm={() => setIsConfirmDialogOpen(true)}
            onOpenReject={() => setIsRejectDialogOpen(true)}
            status={suggestion.status}
          />
        )}

        {activeStep === "apply" && (
          <SuggestionApplyStep
            isApplying={applyMutation.isPending}
            onOpenApply={() => setIsApplyDialogOpen(true)}
            suggestion={suggestion}
          />
        )}

        <SuggestionTechnicalDetails
          duplicateInsight={duplicateInsight}
          logs={logsQuery.data ?? []}
          logsError={logsQuery.isError}
          logsErrorMessage={getSuggestionErrorMessage(logsQuery.error, "Failed to load logs")}
          logsLoading={logsQuery.isLoading}
          suggestion={suggestion}
          unsavedDraftSnapshot={unsavedDraftSnapshot}
        />
      </div>

      <SuggestionActionDialog
        confirmLabel={confirmMutation.isPending ? "Confirming..." : "Confirm"}
        description="This will move suggestion status to approved and lock draft editing."
        isBusy={confirmMutation.isPending}
        onClose={() => setIsConfirmDialogOpen(false)}
        onConfirm={() => void handleConfirm()}
        open={isConfirmDialogOpen}
        title="Confirm suggestion"
      />

      <SuggestionActionDialog
        confirmLabel={rejectMutation.isPending ? "Rejecting..." : "Reject"}
        description="Rejecting will mark this suggestion as rejected."
        isBusy={rejectMutation.isPending}
        onClose={() => setIsRejectDialogOpen(false)}
        onConfirm={() => void handleReject()}
        open={isRejectDialogOpen}
        title="Reject suggestion"
      >
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">Reason (optional)</p>
          <Textarea
            onChange={(event) => setRejectReasonInput(event.target.value)}
            placeholder="Why are you rejecting this suggestion?"
            rows={3}
            value={rejectReasonInput}
          />
        </div>
      </SuggestionActionDialog>

      <SuggestionActionDialog
        confirmLabel={applyMutation.isPending ? "Applying..." : "Apply"}
        description="This will apply the approved suggestion to real rule data."
        isBusy={applyMutation.isPending}
        onClose={() => setIsApplyDialogOpen(false)}
        onConfirm={() => void handleApply()}
        open={isApplyDialogOpen}
        title="Apply suggestion"
      />

      <SuggestionRuleInspectorDialog
        candidateName={selectedDuplicateCandidate?.name}
        candidateSimilarity={selectedDuplicateCandidate?.similarity}
        draft={draftState ?? suggestion.draft}
        duplicateDecision={duplicateInsight?.duplicateRisk}
        errorMessage={ruleInspectorError}
        existingRule={selectedRuleDetail}
        isLoading={isRuleInspectorLoading}
        mode={ruleInspectorMode}
        onClose={handleCloseRuleInspector}
        onContinueAnyway={handleContinueAnywayFromCompare}
        onEditExistingRule={handleEditExistingRule}
        onRetry={handleRetryLoadRuleDetail}
        open={isRuleInspectorOpen}
      />
    </section>
  );
}
