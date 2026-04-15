import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  type SuggestionStepState,
  suggestionWorkflowSteps,
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
import { resolveDuplicateUiState } from "@/features/suggestions/components/duplicateUiState";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";
import { EmptyState } from "@/shared/ui/empty-state";
import { AppLoadingState } from "@/shared/ui/app-loading-state";
import { FieldHelpText } from "@/shared/ui/field-help-text";
import { Label } from "@/shared/ui/label";
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

const SUGGESTION_STEP_STORAGE_PREFIX = "suggestion-detail-step:";

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

function getSuggestionStepStorageKey(suggestionId: string) {
  return `${SUGGESTION_STEP_STORAGE_PREFIX}${suggestionId}`;
}

function getSuggestionStepIndex(step: SuggestionStepKey) {
  return suggestionWorkflowSteps.findIndex((item) => item.key === step);
}

function getStoredSuggestionStep(suggestionId: string): SuggestionStepKey | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(getSuggestionStepStorageKey(suggestionId));
    if (
      raw === "generate" ||
      raw === "draft" ||
      raw === "simulate" ||
      raw === "review" ||
      raw === "decision" ||
      raw === "apply"
    ) {
      return raw;
    }
  } catch {
    return null;
  }
  return null;
}

function persistSuggestionStep(suggestionId: string, step: SuggestionStepKey) {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(getSuggestionStepStorageKey(suggestionId), step);
  } catch {
    // Ignore storage failures and keep the in-memory step only.
  }
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

function getHttpStatusFromError(error: unknown): number | null {
  if (typeof error !== "object" || error === null) {
    return null;
  }

  const directStatus = (error as { status?: unknown }).status;
  if (typeof directStatus === "number" && Number.isFinite(directStatus)) {
    return directStatus;
  }

  const response = (error as { response?: { status?: unknown } }).response;
  const responseStatus = response?.status;
  if (typeof responseStatus === "number" && Number.isFinite(responseStatus)) {
    return responseStatus;
  }

  return null;
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

  return base;
}

function removeStaleDuplicateCandidates(
  insight: DuplicateInsight | null,
  staleRuleIds: Set<string>
): DuplicateInsight | null {
  if (!insight || staleRuleIds.size === 0) {
    return insight;
  }

  const sourceCandidates = insight.similarRules ?? insight.candidates ?? [];
  const filtered = sourceCandidates.filter((candidate) => !staleRuleIds.has(candidate.rule_id));
  if (filtered.length === sourceCandidates.length) {
    return insight;
  }

  const hasRemaining = filtered.length > 0;
  return {
    ...insight,
    level: hasRemaining ? insight.level : "none",
    duplicateRisk: hasRemaining ? insight.duplicateRisk : "DIFFERENT",
    reason: hasRemaining ? insight.reason : "stale_candidates_removed",
    rationale: hasRemaining ? insight.rationale : "stale_candidates_removed",
    similarRules: filtered,
    candidates: filtered,
  };
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
  const [draftSaveState, setDraftSaveState] = useState<"saved" | "dirty" | "saving" | "error">("saved");
  const [draftValidationError, setDraftValidationError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [staleBanner, setStaleBanner] = useState<string | null>(null);
  const [unsavedDraftSnapshot, setUnsavedDraftSnapshot] = useState<string | null>(null);

  const [simulateResult, setSimulateResult] = useState<RuleSuggestionSimulateOut | null>(null);
  const [simulateError, setSimulateError] = useState<string | null>(null);
  const [hasExplicitReviewAccess, setHasExplicitReviewAccess] = useState(false);

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
  const [staleDuplicateRuleIds, setStaleDuplicateRuleIds] = useState<string[]>([]);
  const initializedSuggestionIdRef = useRef<string | null>(null);
  const ruleInspectorRequestIdRef = useRef(0);
  const workflowContentRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!detailQuery.data) {
      return;
    }

    setDraftState(cloneDraft(detailQuery.data.draft));

    const isNewSuggestion = initializedSuggestionIdRef.current !== detailQuery.data.id;
    if (isNewSuggestion) {
      initializedSuggestionIdRef.current = detailQuery.data.id;
      setStaleDuplicateRuleIds([]);
      const storedStep = getStoredSuggestionStep(detailQuery.data.id);
      const statusAllowsReview =
        detailQuery.data.status === "approved" ||
        detailQuery.data.status === "applied" ||
        detailQuery.data.status === "rejected" ||
        detailQuery.data.status === "expired" ||
        detailQuery.data.status === "failed";
      const storedStepAllowsReview =
        storedStep === "review" || storedStep === "decision" || storedStep === "apply";

      const shouldStartAtGenerate =
        locationState?.initialStep === "generate" &&
        (!locationState?.generationInsights ||
          locationState.generationInsights.suggestionId === detailQuery.data.id);

      setActiveStep(
        shouldStartAtGenerate
          ? "generate"
          : storedStep ?? mapStatusToInitialStep(detailQuery.data.status)
      );
      setHasExplicitReviewAccess(
        shouldStartAtGenerate ? false : statusAllowsReview || storedStepAllowsReview
      );

      if (shouldStartAtGenerate) {
        navigate(location.pathname, { replace: true });
      }
    }

    setDraftValidationError(null);
    setActionError(null);
    setStaleBanner(null);
    setDraftSaveState("saved");
  }, [
    detailQuery.data?.id,
    detailQuery.data?.version,
    location.pathname,
    locationState?.generationInsights?.suggestionId,
    locationState?.initialStep,
    navigate,
  ]);

  useEffect(() => {
    if (!detailQuery.data?.id) {
      return;
    }
    persistSuggestionStep(detailQuery.data.id, activeStep);
  }, [activeStep, detailQuery.data?.id]);

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
    const extracted = extractDuplicateInsight(detailQuery.data, logsQuery.data, locationState);
    return removeStaleDuplicateCandidates(extracted, new Set(staleDuplicateRuleIds));
  }, [detailQuery.data, locationState, logsQuery.data, staleDuplicateRuleIds]);

  const duplicateState = useMemo(
    () =>
      resolveDuplicateUiState({
        decision: duplicateInsight?.duplicateRisk,
        level: duplicateInsight?.level,
        candidatesCount:
          duplicateInsight?.similarRules?.length ?? duplicateInsight?.candidates?.length ?? 0,
        topSimilarity:
          duplicateInsight?.similarRules?.[0]?.similarity ??
          duplicateInsight?.candidates?.[0]?.similarity,
      }),
    [
      duplicateInsight?.candidates,
      duplicateInsight?.duplicateRisk,
      duplicateInsight?.level,
      duplicateInsight?.similarRules,
    ]
  );

  const stepStates = useMemo<Record<SuggestionStepKey, SuggestionStepState>>(() => {
    const unlocked = new Set<SuggestionStepKey>(["generate", "draft"]);
    if (draftState) {
      unlocked.add("simulate");
      unlocked.add("review");
      unlocked.add("decision");
    }
    if (
      hasExplicitReviewAccess ||
      activeStep === "review" ||
      activeStep === "decision" ||
      activeStep === "apply" ||
      suggestionId === undefined ||
      detailQuery.data?.status === "approved" ||
      detailQuery.data?.status === "applied" ||
      detailQuery.data?.status === "rejected" ||
      detailQuery.data?.status === "expired" ||
      detailQuery.data?.status === "failed"
    ) {
      unlocked.add("review");
      unlocked.add("decision");
    }
    if (
      detailQuery.data?.status === "approved" ||
      detailQuery.data?.status === "applied" ||
      activeStep === "apply"
    ) {
      unlocked.add("apply");
    }

    const activeIndex = getSuggestionStepIndex(activeStep);

    return Object.fromEntries(
      suggestionWorkflowSteps.map((step, index) => {
        if (step.key === activeStep) {
          return [step.key, "current"];
        }
        if (!unlocked.has(step.key)) {
          return [step.key, "locked"];
        }
        return [step.key, index < activeIndex ? "done" : "available"];
      })
    ) as Record<SuggestionStepKey, SuggestionStepState>;
  }, [activeStep, detailQuery.data?.status, draftState, hasExplicitReviewAccess, suggestionId]);

  const highlightTerms = useMemo(
    () =>
      (draftState ?? detailQuery.data?.draft)?.context_terms
        ?.map((term) => term.term?.trim())
        .filter((term): term is string => Boolean(term)) ?? [],
    [detailQuery.data?.draft, draftState]
  );

  const showSimulationSemanticNote = useMemo(() => {
    const draft = draftState ?? detailQuery.data?.draft;
    if (!draft) {
      return false;
    }

    const hasSemanticMatchMode = draft.rule?.match_mode === "keyword_plus_semantic";
    const hasNonExactLinkedTerms = (draft.context_terms ?? []).some((term) => {
      if (term.enabled === false) {
        return false;
      }
      const entityType = String(term.entity_type ?? "").trim().toUpperCase();
      return !["INTERNAL_CODE", "CUSTOM_SECRET", "PROPRIETARY_IDENTIFIER"].includes(entityType);
    });

    return hasSemanticMatchMode || hasNonExactLinkedTerms;
  }, [detailQuery.data?.draft, draftState]);

  const goToStep = useCallback((step: SuggestionStepKey) => {
    setActiveStep(step);
  }, []);

  const handleStaleConflict = async (message: string) => {
    setStaleBanner(message);
    setUnsavedDraftSnapshot(draftState ? JSON.stringify(draftState, null, 2) : null);
    setDraftSaveState("error");
    await detailQuery.refetch();
  };

  const saveDraft = useCallback(async (options?: { silent?: boolean }) => {
    if (!detailQuery.data || !draftState || !canEditDraft(detailQuery.data.status)) {
      return false;
    }

    setDraftValidationError(null);
    setActionError(null);
    setStaleBanner(null);
    setDraftSaveState("saving");

    const validationMessage = validateDraft(draftState.rule, draftState.context_terms);
    if (validationMessage) {
      setDraftValidationError(validationMessage);
      setDraftSaveState("error");
      return false;
    }

    try {
      const saved = await editMutation.mutateAsync({
        draft: draftState,
        expected_version: detailQuery.data.version,
      });

      setDraftState(cloneDraft(saved.draft));
      await detailQuery.refetch();
      setDraftSaveState("saved");

      if (!options?.silent) {
        toast({
          title: "Draft saved",
          description: "Suggestion draft has been updated.",
          variant: "success",
        });
      }
      return true;
    } catch (error) {
      if (error instanceof SuggestionApiError && isStaleVersionConflict(error)) {
        await handleStaleConflict(
          "Suggestion was updated elsewhere. Please review the latest data and apply your changes again."
        );
        return false;
      }
      if (error instanceof SuggestionApiError) {
        const fieldMessage = getDraftValidationMessageFromApiError(error);
        if (fieldMessage) {
          setDraftValidationError(fieldMessage);
        }
      }
      const message = getSuggestionErrorMessage(error, "Failed to save draft");
      setActionError(message);
      setDraftSaveState("error");
      if (!options?.silent) {
        toast({
          title: "Save draft failed",
          description: message,
          variant: "destructive",
        });
      }
      return false;
    }
  }, [detailQuery.data, draftState, editMutation, detailQuery, handleStaleConflict]);

  const handleSaveDraft = useCallback(async () => {
    await saveDraft();
  }, [saveDraft]);

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
      setActiveStep("apply");
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
      setActiveStep("apply");
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
      const hasWarnings = !result.runtime_usable || result.runtime_warnings.length > 0;
      toast({
        title: hasWarnings ? "Simulation complete. Review recommended" : "Simulation complete",
        description: `Processed ${result.sample_size} samples.`,
        variant: hasWarnings ? "default" : "success",
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

  const handleContinueToReview = () => {
    setHasExplicitReviewAccess(true);
    setActiveStep("review");
  };

  useEffect(() => {
    workflowContentRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }, [activeStep]);

  useEffect(() => {
    if (!detailQuery.data || !draftState) {
      return;
    }

    if (editMutation.isPending) {
      setDraftSaveState("saving");
      return;
    }

    setDraftSaveState(hasDirtyDraft ? "dirty" : "saved");
  }, [detailQuery.data?.version, draftState, editMutation.isPending, hasDirtyDraft]);

  useEffect(() => {
    if (
      activeStep !== "draft" ||
      !detailQuery.data ||
      !draftState ||
      !canEditDraft(detailQuery.data.status) ||
      !hasDirtyDraft ||
      editMutation.isPending
    ) {
      return;
    }

    const validationMessage = validateDraft(draftState.rule, draftState.context_terms);
    if (validationMessage) {
      setDraftSaveState("error");
      return;
    }

    const timer = window.setTimeout(() => {
      void saveDraft({ silent: true });
    }, 1200);

    return () => window.clearTimeout(timer);
  }, [activeStep, detailQuery.data, draftState, editMutation.isPending, hasDirtyDraft, saveDraft]);

  useEffect(() => {
    if (stepStates[activeStep] !== "locked") {
      return;
    }
    setActiveStep(detailQuery.data?.status === "approved" || detailQuery.data?.status === "applied" ? "review" : "draft");
  }, [activeStep, detailQuery.data?.status, stepStates]);

  const markDuplicateCandidateStale = useCallback((ruleId: string) => {
    const normalized = String(ruleId ?? "").trim();
    if (!normalized) {
      return;
    }
    setStaleDuplicateRuleIds((previous) =>
      previous.includes(normalized) ? previous : [...previous, normalized]
    );
  }, []);

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
      const status = getHttpStatusFromError(error);
      if (status === 404) {
        markDuplicateCandidateStale(candidate.rule_id);
        setSelectedDuplicateCandidate((previous) =>
          previous?.rule_id === candidate.rule_id ? null : previous
        );
        setIsRuleInspectorOpen(false);
        setStaleBanner(
          "One duplicate candidate was removed because the rule no longer exists."
        );
        toast({
          title: "Duplicate candidate removed",
          description: "That similar rule was deleted. The duplicate list has been refreshed.",
          variant: "default",
        });
        setRuleInspectorError(
          "This duplicate rule no longer exists and was removed from the current view."
        );
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
    if (String(selectedDuplicateCandidate.origin ?? "").toLowerCase().includes("global")) {
      return;
    }

    const ruleId = encodeURIComponent(selectedDuplicateCandidate.rule_id);
    handleCloseRuleInspector();
    navigate(
      `/app/settings/rules?editRuleId=${ruleId}&source=suggestion-compare&returnToSuggestionId=${encodeURIComponent(
        suggestion.id
      )}&returnStep=generate`
    );
  };

  const handleContinueAnywayFromCompare = () => {
    handleCloseRuleInspector();
    setActiveStep("draft");
  };

  if (!isRuleSetResolved) {
    return (
      <section className="p-6">
        <AppLoadingState
          className="mx-auto max-w-3xl"
          description="We are resolving the current workspace before loading this suggestion."
          title="Loading suggestion"
        />
      </section>
    );
  }

  if (!currentRuleSetId) {
    return <Navigate replace to="/onboarding/rule-set" />;
  }

  if (detailQuery.isLoading) {
    return (
      <section className="p-6">
        <AppLoadingState
          className="mx-auto max-w-3xl"
          description="Loading the suggestion details and workflow state."
          title="Loading suggestion"
        />
      </section>
    );
  }

  if (detailQuery.isError || !detailQuery.data) {
    const status = detailQuery.error instanceof SuggestionApiError ? detailQuery.error.status : undefined;

    if (status === 403) {
      return (
        <section className="p-6">
          <AppAlert
            description="You do not have permission to view this suggestion."
            title="Access denied"
            variant="error"
          />
        </section>
      );
    }

    if (status === 404) {
      return (
        <section className="p-6">
          <EmptyState
            description="The suggestion may have been deleted or is no longer available."
            title="Suggestion not found"
          />
        </section>
      );
    }

    return (
      <section className="p-6">
        <AppAlert
          description={getSuggestionErrorMessage(detailQuery.error, "Failed to load suggestion detail")}
          title="Suggestion unavailable"
          variant="error"
        />
      </section>
    );
  }

  const suggestion = detailQuery.data;

  return (
    <section className="h-full overflow-auto p-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4">
        <AppSectionCard className="p-5 md:p-6" contentClassName="space-y-0">
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
        </AppSectionCard>

        {staleBanner && (
          <AppAlert description={staleBanner} title="Suggestion changed" variant="warning" />
        )}

        {actionError && (
          <AppAlert description={actionError} title="Action failed" variant="error" />
        )}

        <SuggestionStepper
          activeStep={activeStep}
          onStepChange={(step) => {
            if (stepStates[step] !== "locked") {
              goToStep(step);
            }
          }}
          stepStates={stepStates}
        />

        <div ref={workflowContentRef}>
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
              onBack={() => goToStep("generate")}
              onContinue={() => goToStep("simulate")}
              onDraftChange={setDraftState}
              onSaveDraft={() => void handleSaveDraft()}
              saveState={draftSaveState}
              status={suggestion.status}
              validationError={draftValidationError}
            />
          )}

          {activeStep === "simulate" && (
            <SuggestionSimulateStep
              errorMessage={simulateError}
              highlightTerms={highlightTerms}
              isSubmitting={simulateMutation.isPending}
              onBack={() => goToStep("draft")}
              onContinue={handleContinueToReview}
              onSimulate={handleSimulate}
              result={simulateResult}
              showSemanticNote={showSimulationSemanticNote}
              status={suggestion.status}
            />
          )}

          {activeStep === "review" && (
            <SuggestionReviewStep
              onBack={() => goToStep("simulate")}
              onContinue={() => goToStep("decision")}
              suggestion={suggestion}
            />
          )}

          {activeStep === "decision" && (
            <SuggestionDecisionStep
              duplicateRisk={duplicateState === "EXACT_DUPLICATE" ? "Exact duplicate" : duplicateInsight?.duplicateRisk}
              isConfirming={confirmMutation.isPending}
              isRejecting={rejectMutation.isPending}
              onBack={() => goToStep("review")}
              onOpenConfirm={() => setIsConfirmDialogOpen(true)}
              onOpenReject={() => setIsRejectDialogOpen(true)}
              runtimeUsable={suggestion.quality_signals?.runtime_usable}
              runtimeWarnings={suggestion.quality_signals?.runtime_warnings ?? []}
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
        </div>

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

      <ConfirmDialog
        confirmLabel={confirmMutation.isPending ? "Confirming..." : "Confirm"}
        description="This will move suggestion status to approved and lock draft editing."
        isBusy={confirmMutation.isPending}
        onClose={() => setIsConfirmDialogOpen(false)}
        onConfirm={() => void handleConfirm()}
        open={isConfirmDialogOpen}
        title="Confirm suggestion"
      >
        {typeof duplicateInsight?.duplicateRisk === "string" &&
        !["", "none", "different", "low"].includes(duplicateInsight.duplicateRisk.trim().toLowerCase()) ? (
          <AppAlert
            description="Duplicate signal is still present for this suggestion. Review compare and generate steps before confirming."
            title="Duplicate warning"
            variant="warning"
          />
        ) : null}
        {!suggestion.quality_signals?.runtime_usable ||
        (suggestion.quality_signals?.runtime_warnings?.length ?? 0) > 0 ? (
          <AppAlert
            description={
              <div className="space-y-1">
                <p>May not work as expected at runtime, but you can still confirm and apply this suggestion.</p>
                {(suggestion.quality_signals?.runtime_warnings ?? []).map((warning) => (
                  <p key={warning}>{warning}</p>
                ))}
              </div>
            }
            title="Runtime usability: warning"
            variant="warning"
          />
        ) : null}
      </ConfirmDialog>

      <SuggestionActionDialog
        confirmLabel={rejectMutation.isPending ? "Rejecting..." : "Reject"}
        description="Rejecting will mark this suggestion as rejected."
        isBusy={rejectMutation.isPending}
        onClose={() => setIsRejectDialogOpen(false)}
        onConfirm={() => void handleReject()}
        open={isRejectDialogOpen}
        title="Reject suggestion"
        confirmVariant="danger"
      >
        <div className="space-y-2">
          <Label htmlFor="suggestion-reject-reason">Reason</Label>
          <Textarea
            id="suggestion-reject-reason"
            onChange={(event) => setRejectReasonInput(event.target.value)}
            placeholder="Why are you rejecting this suggestion?"
            rows={3}
            value={rejectReasonInput}
          />
          <FieldHelpText>Optional context for reviewers who revisit this suggestion later.</FieldHelpText>
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
        candidateOrigin={selectedDuplicateCandidate?.origin}
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

function getDraftValidationMessageFromApiError(error: SuggestionApiError): string | null {
  const details = Array.isArray(error.details) ? error.details : [];
  for (const detail of details) {
    const field = String(detail.field ?? "").trim().toLowerCase();
    const reason = String(detail.reason ?? "").trim().toLowerCase();
    if (field === "draft.rule.stable_key" || field === "stable_key") {
      if (reason === "global_rule_key_reserved") {
        return "Stable key is reserved by a global rule.";
      }
      if (reason === "existing_rule_would_be_overwritten") {
        return "Stable key already exists in Rules and would overwrite an existing rule.";
      }
    }
  }
  return null;
}
