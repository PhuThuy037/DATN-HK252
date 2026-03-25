import {
  FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { cn } from "@/shared/lib/utils";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import { Textarea } from "@/shared/ui/textarea";
import { toast } from "@/shared/ui/use-toast";
import { RuleForm } from "@/features/rules/components/RuleForm";
import {
  useCreateRule,
  useDebugEvaluate,
  useDeleteRule,
  useEffectiveRules,
  useRuleChangeLogs,
  useRules,
  useToggleGlobalRule,
  useUpdateRule,
} from "@/features/rules/hooks";
import { useRuleSetStore } from "@/features/rules/store/ruleSetStore";
import type {
  CreateRuleRequest,
  DebugEvaluateResponse,
  Rule,
  RuleDebugMatch,
  UpdateRuleRequest,
} from "@/features/rules/types";

type RulesPageLocationState = {
  highlightRuleId?: string;
  openEditForRuleId?: string;
  source?: string;
};

function formatDateTime(value?: string) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function isGlobalRule(rule: Rule) {
  const origin = (rule.origin ?? "").toLowerCase();
  return origin.includes("global") || origin.includes("override");
}

function hasRuleFormFieldErrorResponse(error: unknown) {
  const response = (error as { response?: { data?: unknown; status?: number } } | null)?.response;
  const status = response?.status;
  if (status !== 409 && status !== 422) {
    return false;
  }

  const responseData = response?.data;
  if (!responseData || typeof responseData !== "object") {
    return false;
  }

  const envelopeError = (responseData as { error?: { details?: unknown } }).error;
  return Array.isArray(envelopeError?.details) && envelopeError.details.length > 0;
}

function RuleModal({
  title,
  open,
  onClose,
  children,
}: {
  title: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="max-h-[90vh] w-full max-w-2xl overflow-y-auto p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <Button onClick={onClose} size="sm" type="button" variant="outline">
            Close
          </Button>
        </div>
        {children}
      </Card>
    </div>
  );
}

function DeleteRuleDialog({
  rule,
  isDeleting,
  open,
  onCancel,
  onConfirm,
}: {
  rule: Rule | null;
  isDeleting: boolean;
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const titleId = useId();
  const descriptionId = useId();
  const cancelButtonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    cancelButtonRef.current?.focus();

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [onCancel, open]);

  if (!open || !rule) {
    return null;
  }

  const handleOverlayKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      onCancel();
    }
  };

  return (
    <div
      aria-describedby={descriptionId}
      aria-labelledby={titleId}
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onCancel}
      onKeyDown={handleOverlayKeyDown}
      role="dialog"
    >
      <Card
        className="w-full max-w-md space-y-4 p-5 shadow-lg"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="space-y-2">
          <h3 className="text-lg font-semibold" id={titleId}>
            Delete rule?
          </h3>
          <div className="space-y-2 text-sm text-muted-foreground" id={descriptionId}>
            <p>
              Are you sure you want to delete{" "}
              <span className="font-semibold text-foreground">"{rule.name}"</span>?
            </p>
            <p>This action cannot be undone.</p>
          </div>
        </div>

        <div className="rounded-lg border bg-muted/30 p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Rule
          </p>
          <p className="mt-1 text-sm font-semibold">{rule.name}</p>
          <p className="mt-1 break-all text-xs text-muted-foreground">{rule.stable_key ?? "-"}</p>
        </div>

        <div className="flex justify-end gap-2">
          <Button
            disabled={isDeleting}
            onClick={onCancel}
            ref={cancelButtonRef}
            type="button"
            variant="outline"
          >
            Cancel
          </Button>
          <Button
            className="bg-rose-600 text-white hover:bg-rose-700"
            disabled={isDeleting}
            onClick={onConfirm}
            type="button"
          >
            {isDeleting ? "Deleting..." : "Delete"}
          </Button>
        </div>
      </Card>
    </div>
  );
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function formatActionLabel(value?: string | null) {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (!normalized) {
    return "Unknown";
  }
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function getActionBadgeClass(action?: string | null) {
  switch (String(action ?? "").trim().toLowerCase()) {
    case "block":
      return "border-rose-300 bg-rose-50 text-rose-700";
    case "mask":
      return "border-amber-300 bg-amber-50 text-amber-700";
    case "allow":
      return "border-emerald-300 bg-emerald-50 text-emerald-700";
    default:
      return "border-slate-300 bg-slate-100 text-slate-700";
  }
}

function formatDebugNumber(value: unknown) {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) {
    return "-";
  }
  return numeric.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function formatSummaryValue(value: unknown, emptyLabel = "none") {
  if (Array.isArray(value)) {
    const items = value
      .map((item) => String(item ?? "").trim())
      .filter(Boolean);
    return items.length > 0 ? items.join(", ") : emptyLabel;
  }

  if (value == null) {
    return emptyLabel;
  }

  if (typeof value === "boolean") {
    return value ? "yes" : "no";
  }

  if (typeof value === "number") {
    return formatDebugNumber(value);
  }

  const text = String(value).trim();
  return text ? text : emptyLabel;
}

function sortDebugMatches(matches: RuleDebugMatch[]) {
  return [...matches].sort((left, right) => {
    const rightPriority = right.priority ?? Number.NEGATIVE_INFINITY;
    const leftPriority = left.priority ?? Number.NEGATIVE_INFINITY;
    return rightPriority - leftPriority;
  });
}

function isSameDebugMatch(left?: RuleDebugMatch | null, right?: RuleDebugMatch | null) {
  if (!left || !right) {
    return false;
  }

  if (left.rule_id && right.rule_id) {
    return left.rule_id === right.rule_id;
  }

  if (left.stable_key && right.stable_key) {
    return left.stable_key === right.stable_key;
  }

  return (
    left.name === right.name &&
    left.action === right.action &&
    left.priority === right.priority
  );
}

function getPrimaryDebugMatch(matches: RuleDebugMatch[], finalAction?: string) {
  if (matches.length === 0) {
    return null;
  }

  const normalizedFinalAction = String(finalAction ?? "").trim().toLowerCase();
  return (
    matches.find(
      (match) => String(match.action ?? "").trim().toLowerCase() === normalizedFinalAction
    ) ?? matches[0]
  );
}

function getExtraDebugOutput(result: DebugEvaluateResponse) {
  const { final_action, matched_rules, signals, ...rest } = result;
  return rest;
}

function getDebugSummaryExplanation(
  result: DebugEvaluateResponse,
  primaryMatch: RuleDebugMatch | null
) {
  const actionLabel = formatActionLabel(result.final_action);
  const signals = result.signals ?? {};
  const security = asRecord(signals.security);
  const securityReason = String(security?.reason ?? "").trim();

  if (primaryMatch) {
    const ruleName = primaryMatch.name?.trim();
    const stableKeyValue = primaryMatch.stable_key?.trim();
    const ruleLabel = ruleName || stableKeyValue || "Matched rule";
    const stableKey = ruleName && stableKeyValue
      ? ` (${primaryMatch.stable_key?.trim()})`
      : "";
    const priorityLabel =
      primaryMatch.priority != null ? `priority ${primaryMatch.priority}` : "current priority";

    return `${actionLabel} because "${ruleLabel}"${stableKey} matched with ${String(
      primaryMatch.action ?? result.final_action ?? "allow"
    )
      .trim()
      .toLowerCase()} at ${priorityLabel}.`;
  }

  if (securityReason) {
    return `${actionLabel} with no matching rule found. Security scan reason: ${securityReason}.`;
  }

  if (String(result.final_action ?? "").trim().toLowerCase() === "allow") {
    return "No matching rule found. The input remains allowed under the current rule set.";
  }

  return `${actionLabel} without a visible rule match. Review technical details for the raw engine output.`;
}

function DebugSummaryField({
  label,
  value,
  helper,
}: {
  label: string;
  value: ReactNode;
  helper?: string;
}) {
  return (
    <div className="rounded-lg border bg-background p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <div className="mt-1 text-sm font-medium text-foreground">{value}</div>
      {helper && <p className="mt-1 text-xs text-muted-foreground">{helper}</p>}
    </div>
  );
}

function DebugEvaluateResult({ result }: { result: DebugEvaluateResponse }) {
  const matchedRules = sortDebugMatches(result.matched_rules ?? []);
  const primaryMatch = getPrimaryDebugMatch(matchedRules, result.final_action);
  const signals = result.signals ?? {};
  const security = asRecord(signals.security);
  const securityDecision = formatSummaryValue(security?.decision);
  const securityReason = String(security?.reason ?? "").trim();
  const extraDebugOutput = getExtraDebugOutput(result);
  const hasExtraDebugOutput = Object.keys(extraDebugOutput).length > 0;

  return (
    <div className="space-y-4">
      <Card className="space-y-5 p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Summary
            </p>
            <h3 className="text-base font-semibold">Evaluation result</h3>
            <p className="max-w-3xl text-sm text-muted-foreground">
              {getDebugSummaryExplanation(result, primaryMatch)}
            </p>
          </div>

          <div className="rounded-lg border bg-muted/40 px-3 py-2">
            <p className="text-xs text-muted-foreground">Final action</p>
            <div className="mt-2">
              <Badge className={cn("capitalize", getActionBadgeClass(result.final_action))}>
                {formatActionLabel(result.final_action)}
              </Badge>
            </div>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[1.3fr_0.9fr]">
          <section className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-sm font-semibold">Matched rules</h4>
              <Badge className="bg-muted text-muted-foreground">
                {matchedRules.length} {matchedRules.length === 1 ? "rule" : "rules"}
              </Badge>
            </div>

            {matchedRules.length === 0 ? (
              <div className="rounded-lg border border-dashed p-4">
                <p className="text-sm font-medium">No matching rule found</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  This input followed the default decision path for the current rule set.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {matchedRules.map((rule, index) => {
                  const isPrimary = isSameDebugMatch(rule, primaryMatch) || (!primaryMatch && index === 0);
                  return (
                    <div
                      className={cn(
                        "rounded-lg border p-3",
                        isPrimary && "border-primary/40 bg-primary/5"
                      )}
                      key={rule.rule_id ?? rule.stable_key ?? `${rule.name ?? "rule"}-${index}`}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <p className="text-sm font-semibold">{rule.name?.trim() || "Unnamed rule"}</p>
                          <p className="mt-1 break-all text-xs text-muted-foreground">
                            {rule.stable_key?.trim() || "No stable key"}
                          </p>
                        </div>

                        <div className="flex flex-wrap items-center gap-2">
                          {isPrimary && (
                            <Badge className="border-primary/40 bg-primary/10 text-primary">
                              Main match
                            </Badge>
                          )}
                          <Badge className={cn("capitalize", getActionBadgeClass(rule.action))}>
                            {formatActionLabel(rule.action)}
                          </Badge>
                        </div>
                      </div>

                      <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted-foreground">
                        <span>Priority: {rule.priority ?? "-"}</span>
                        <span>Rule ID: {rule.rule_id ?? "-"}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <section className="space-y-3">
            <h4 className="text-sm font-semibold">Key signals</h4>
            <div className="grid gap-2">
              <DebugSummaryField
                label="Context keywords"
                value={formatSummaryValue(signals.context_keywords)}
              />
              <DebugSummaryField label="Persona" value={formatSummaryValue(signals.persona)} />
              <DebugSummaryField
                helper={securityReason || undefined}
                label="Security decision"
                value={securityDecision}
              />
              <DebugSummaryField
                label="Risk boost"
                value={formatSummaryValue(signals.risk_boost, "0")}
              />
            </div>
          </section>
        </div>
      </Card>

      <Card className="p-4">
        <details>
          <summary className="cursor-pointer text-sm font-semibold">Technical details</summary>
          <p className="mt-2 text-xs text-muted-foreground">
            Raw debug payload is preserved here for deeper inspection.
          </p>

          <div className="mt-3 space-y-3">
            <details className="rounded-md border p-3 text-xs">
              <summary className="cursor-pointer font-medium text-muted-foreground">
                Raw matched rules JSON
              </summary>
              <pre className="mt-2 overflow-auto rounded-md bg-muted p-2 text-[11px]">
                {JSON.stringify(result.matched_rules ?? [], null, 2)}
              </pre>
            </details>

            <details className="rounded-md border p-3 text-xs">
              <summary className="cursor-pointer font-medium text-muted-foreground">
                Raw signals JSON
              </summary>
              <pre className="mt-2 overflow-auto rounded-md bg-muted p-2 text-[11px]">
                {JSON.stringify(result.signals ?? {}, null, 2)}
              </pre>
            </details>

            <details className="rounded-md border p-3 text-xs">
              <summary className="cursor-pointer font-medium text-muted-foreground">
                Extra engine/debug output
              </summary>
              {hasExtraDebugOutput ? (
                <pre className="mt-2 overflow-auto rounded-md bg-muted p-2 text-[11px]">
                  {JSON.stringify(extraDebugOutput, null, 2)}
                </pre>
              ) : (
                <p className="mt-2 text-muted-foreground">
                  No additional engine debug fields were returned for this run.
                </p>
              )}
            </details>
          </div>
        </details>
      </Card>
    </div>
  );
}

export function RulesPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const locationState = (location.state as RulesPageLocationState | null) ?? null;
  const searchParams = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const editRuleIdFromQuery = searchParams.get("editRuleId")?.trim() ?? "";
  const sourceFromQuery = searchParams.get("source")?.trim() ?? "";
  const returnToSuggestionId = searchParams.get("returnToSuggestionId")?.trim() ?? "";
  const returnStep = searchParams.get("returnStep")?.trim() ?? "";
  const [createOpen, setCreateOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<Rule | null>(null);
  const [rulePendingDelete, setRulePendingDelete] = useState<Rule | null>(null);
  const [debugContent, setDebugContent] = useState("");
  const [activeTab, setActiveTab] = useState("my-rules");

  const currentRuleSetId = useRuleSetStore((state) => state.currentRuleSetId);
  const currentRuleSet = useRuleSetStore((state) => state.currentRuleSet);
  const isRuleSetResolved = useRuleSetStore((state) => state.isRuleSetResolved);

  const rulesQuery = useRules(currentRuleSetId ?? undefined);
  const effectiveRulesQuery = useEffectiveRules();
  const changeLogsQuery = useRuleChangeLogs(currentRuleSetId ?? undefined, { limit: 50 });
  const createRuleMutation = useCreateRule(currentRuleSetId ?? undefined);
  const updateRuleMutation = useUpdateRule(currentRuleSetId ?? undefined);
  const deleteRuleMutation = useDeleteRule(currentRuleSetId ?? undefined);
  const toggleGlobalRuleMutation = useToggleGlobalRule(currentRuleSetId ?? undefined);
  const debugEvaluateMutation = useDebugEvaluate();

  const rules = useMemo(() => rulesQuery.data ?? [], [rulesQuery.data]);
  const myRules = useMemo(() => rules.filter((rule) => !isGlobalRule(rule)), [rules]);
  const globalRules = useMemo(() => rules.filter((rule) => isGlobalRule(rule)), [rules]);
  const changeLogs = useMemo(() => changeLogsQuery.data ?? [], [changeLogsQuery.data]);
  const effectiveRules = useMemo(
    () => effectiveRulesQuery.data ?? [],
    [effectiveRulesQuery.data]
  );

  useEffect(() => {
    const targetRuleId = editRuleIdFromQuery || locationState?.openEditForRuleId?.trim() || "";
    if (!targetRuleId || rules.length === 0) {
      return;
    }

    const targetRule = rules.find((rule) => rule.id === targetRuleId);
    if (targetRule) {
      setActiveTab(isGlobalRule(targetRule) ? "global-rules" : "my-rules");
      setEditingRule(targetRule);
    } else {
      toast({
        title: "Rule not found",
        description: "Unable to open the requested rule for editing.",
        variant: "destructive",
      });
    }

    navigate(location.pathname, { replace: true });
  }, [editRuleIdFromQuery, location.pathname, locationState?.openEditForRuleId, navigate, rules]);

  const handleCreateRule = async (payload: CreateRuleRequest | UpdateRuleRequest) => {
    try {
      await createRuleMutation.mutateAsync(payload as CreateRuleRequest);
      toast({
        title: "Rule created",
        description: "Rule has been created successfully.",
        variant: "success",
      });
      setCreateOpen(false);
    } catch (error) {
      if (!hasRuleFormFieldErrorResponse(error)) {
        toast({
          title: "Create failed",
          description: error instanceof Error ? error.message : "Failed to create rule.",
          variant: "destructive",
        });
      }
      throw error;
    }
  };

  const handleUpdateRule = async (payload: CreateRuleRequest | UpdateRuleRequest) => {
    if (!editingRule) {
      return;
    }
    try {
      await updateRuleMutation.mutateAsync({
        ruleId: editingRule.id,
        payload: payload as UpdateRuleRequest,
      });
      toast({
        title: "Rule updated",
        description: "Rule has been updated successfully.",
        variant: "success",
      });
      if (sourceFromQuery === "suggestion-compare" && returnToSuggestionId) {
        navigate(`/app/suggestions/${encodeURIComponent(returnToSuggestionId)}`, {
          state: {
            initialStep: returnStep === "generate" ? "generate" : "draft",
          },
        });
        return;
      }
      setEditingRule(null);
    } catch (error) {
      if (!hasRuleFormFieldErrorResponse(error)) {
        toast({
          title: "Update failed",
          description: error instanceof Error ? error.message : "Failed to update rule.",
          variant: "destructive",
        });
      }
      throw error;
    }
  };

  const handleRequestDeleteRule = (rule: Rule) => {
    setRulePendingDelete(rule);
  };

  const handleCancelDeleteRule = () => {
    if (deleteRuleMutation.isPending) {
      return;
    }
    setRulePendingDelete(null);
  };

  const handleConfirmDeleteRule = async () => {
    if (!rulePendingDelete) {
      return;
    }

    try {
      await deleteRuleMutation.mutateAsync(rulePendingDelete.id);
      toast({
        title: "Rule deleted",
        description: "Rule deleted successfully.",
        variant: "success",
      });
      setRulePendingDelete(null);
    } catch (error) {
      toast({
        title: "Delete failed",
        description: error instanceof Error ? error.message : "Failed to delete rule.",
        variant: "destructive",
      });
    }
  };

  const handleToggleEnabled = async (rule: Rule, enabled: boolean) => {
    try {
      if (isGlobalRule(rule)) {
        if (!rule.stable_key) {
          toast({
            title: "Global rule is read-only",
            description: "This global rule cannot be toggled because stable key is missing.",
            variant: "destructive",
          });
          return;
        }

        await toggleGlobalRuleMutation.mutateAsync({
          stableKey: rule.stable_key,
          payload: { enabled },
        });
      } else {
        await updateRuleMutation.mutateAsync({
          ruleId: rule.id,
          payload: { enabled },
        });
      }

      toast({
        title: "Rule updated",
        description: `Rule ${enabled ? "enabled" : "disabled"} successfully.`,
        variant: "success",
      });
    } catch (error) {
      toast({
        title: "Toggle failed",
        description: error instanceof Error ? error.message : "Failed to toggle rule.",
        variant: "destructive",
      });
    }
  };

  const handleEvaluate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const content = debugContent.trim();
    if (!content) {
      return;
    }

    try {
      await debugEvaluateMutation.mutateAsync({ content });
    } catch (error) {
      toast({
        title: "Evaluate failed",
        description: error instanceof Error ? error.message : "Failed to evaluate text.",
        variant: "destructive",
      });
    }
  };

  if (!isRuleSetResolved) {
    return <p className="p-6 text-sm text-muted-foreground">Resolving workspace...</p>;
  }

  if (!currentRuleSetId) {
    return <Navigate replace to="/onboarding/rule-set" />;
  }

  return (
    <section className="h-full overflow-auto p-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold">Rules Management</h1>
            <p className="text-sm text-muted-foreground">
              Rules below belong to your current workspace rule set.
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Workspace: {currentRuleSet?.name ?? "Current rule set"}
            </p>
          </div>

          {activeTab === "my-rules" && (
            <Button onClick={() => setCreateOpen(true)} type="button">
              New Rule
            </Button>
          )}
        </header>

        <Tabs onValueChange={setActiveTab} value={activeTab}>
          <TabsList className="flex flex-wrap">
            <TabsTrigger value="my-rules">My Rules</TabsTrigger>
            <TabsTrigger value="global-rules">Global Rules</TabsTrigger>
            <TabsTrigger value="effective-rules">Effective Rules</TabsTrigger>
            <TabsTrigger value="change-logs">Change Logs</TabsTrigger>
            <TabsTrigger value="debug">Debug Evaluate</TabsTrigger>
          </TabsList>

          <TabsContent value="my-rules">
            <Card className="p-4">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-base font-semibold">Custom rules in this rule set</h2>
                <Badge>{myRules.length} rules</Badge>
              </div>
              <RuleTable
                allowEdit
                allowDelete
                allowToggle
                emptyText="No custom rules yet. Create your first rule."
                isError={rulesQuery.isError}
                isLoading={rulesQuery.isLoading}
                onDeleteRule={handleRequestDeleteRule}
                onEditRule={setEditingRule}
                onToggleEnabled={handleToggleEnabled}
                rules={myRules}
                showOrigin
              />
            </Card>
          </TabsContent>

          <TabsContent value="global-rules">
            <Card className="p-4">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-base font-semibold">Global rules (read-only)</h2>
                <Badge className="bg-muted text-muted-foreground">
                  {globalRules.length} rules
                </Badge>
              </div>
              <RuleTable
                allowDelete={false}
                allowEdit={false}
                allowToggle
                emptyText="No global rules available."
                isError={rulesQuery.isError}
                isLoading={rulesQuery.isLoading}
                onDeleteRule={handleRequestDeleteRule}
                onEditRule={setEditingRule}
                onToggleEnabled={handleToggleEnabled}
                rules={globalRules}
                showOrigin
              />
            </Card>
          </TabsContent>

          <TabsContent value="effective-rules">
            <Card className="space-y-3 p-4">
              <h2 className="text-base font-semibold">Effective rules</h2>

              {effectiveRulesQuery.isLoading && (
                <p className="text-sm text-muted-foreground">Loading effective rules...</p>
              )}

              {effectiveRulesQuery.isError && (
                <p className="text-sm text-destructive">Failed to load effective rules.</p>
              )}

              {!effectiveRulesQuery.isLoading &&
                !effectiveRulesQuery.isError &&
                effectiveRules.length === 0 && (
                  <p className="text-sm text-muted-foreground">No effective rules found.</p>
                )}

              {effectiveRules.map((rule) => (
                <div className="rounded-md border p-3 text-sm" key={rule.id ?? rule.stable_key}>
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium">{rule.name}</p>
                    <Badge>{rule.action}</Badge>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
                    <span>Priority: {rule.priority ?? "-"}</span>
                    <span>Enabled: {rule.enabled ? "yes" : "no"}</span>
                    <span>Origin: {rule.origin ?? "-"}</span>
                  </div>
                </div>
              ))}
            </Card>
          </TabsContent>

          <TabsContent value="change-logs">
            <Card className="space-y-3 p-4">
              <h2 className="text-base font-semibold">Rule change logs</h2>

              {changeLogsQuery.isLoading && (
                <p className="text-sm text-muted-foreground">Loading change logs...</p>
              )}
              {changeLogsQuery.isError && (
                <p className="text-sm text-destructive">Failed to load change logs.</p>
              )}
              {!changeLogsQuery.isLoading &&
                !changeLogsQuery.isError &&
                changeLogs.length === 0 && (
                  <p className="text-sm text-muted-foreground">No change logs yet.</p>
                )}

              {changeLogs.map((log, index) => (
                <div className="rounded-lg border p-3 text-sm" key={log.id ?? `${index}-${log.created_at}`}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium">{log.action ?? "unknown_action"}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatDateTime(log.created_at)}
                    </p>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Reason: {log.reason ?? "-"}
                  </p>
                  <details className="mt-2 text-xs">
                    <summary className="cursor-pointer text-muted-foreground">
                      Raw JSON
                    </summary>
                    <pre className="mt-2 overflow-auto rounded bg-muted p-2">
                      {JSON.stringify(
                        {
                          changed_fields: log.changed_fields,
                          before_json: log.before_json,
                          after_json: log.after_json,
                        },
                        null,
                        2
                      )}
                    </pre>
                  </details>
                </div>
              ))}
            </Card>
          </TabsContent>

          <TabsContent value="debug">
            <Card className="space-y-5 p-4">
              <div>
                <h2 className="text-base font-semibold">Debug evaluate</h2>
                <p className="text-sm text-muted-foreground">
                  Quick test text against current rules.
                </p>
              </div>

              <form className="space-y-3" onSubmit={handleEvaluate}>
                <Textarea
                  className="min-h-[140px]"
                  onChange={(event) => setDebugContent(event.target.value)}
                  placeholder="Paste or type content to evaluate against the current rule set."
                  value={debugContent}
                />
                <div className="flex justify-end">
                  <Button
                    disabled={debugEvaluateMutation.isPending || !debugContent.trim()}
                    type="submit"
                  >
                    {debugEvaluateMutation.isPending ? "Evaluating..." : "Evaluate"}
                  </Button>
                </div>
              </form>

              {debugEvaluateMutation.isError && (
                <p className="text-sm text-destructive">Failed to evaluate text.</p>
              )}

              {debugEvaluateMutation.data && <DebugEvaluateResult result={debugEvaluateMutation.data} />}
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      <RuleModal onClose={() => setCreateOpen(false)} open={createOpen} title="Create new rule">
        <RuleForm
          isSubmitting={createRuleMutation.isPending}
          mode="create"
          onCancel={() => setCreateOpen(false)}
          onSubmit={handleCreateRule}
        />
      </RuleModal>

      <RuleModal
        onClose={() => setEditingRule(null)}
        open={Boolean(editingRule)}
        title="Edit rule"
      >
        <RuleForm
          initialRule={editingRule}
          isSubmitting={updateRuleMutation.isPending}
          mode="edit"
          onCancel={() => setEditingRule(null)}
          onSubmit={handleUpdateRule}
        />
      </RuleModal>

      <DeleteRuleDialog
        isDeleting={deleteRuleMutation.isPending}
        onCancel={handleCancelDeleteRule}
        onConfirm={() => void handleConfirmDeleteRule()}
        open={Boolean(rulePendingDelete)}
        rule={rulePendingDelete}
      />
    </section>
  );
}

function RuleTable({
  rules,
  isLoading,
  isError,
  emptyText,
  allowEdit,
  allowDelete,
  allowToggle,
  showOrigin,
  onEditRule,
  onDeleteRule,
  onToggleEnabled,
}: {
  rules: Rule[];
  isLoading: boolean;
  isError: boolean;
  emptyText: string;
  allowEdit: boolean;
  allowDelete: boolean;
  allowToggle: boolean;
  showOrigin?: boolean;
  onEditRule: (rule: Rule) => void;
  onDeleteRule: (rule: Rule) => void;
  onToggleEnabled: (rule: Rule, enabled: boolean) => void;
}) {
  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading rules...</p>;
  }

  if (isError) {
    return <p className="text-sm text-destructive">Failed to load rules.</p>;
  }

  if (rules.length === 0) {
    return <p className="text-sm text-muted-foreground">{emptyText}</p>;
  }

  return (
    <ScrollArea className="max-h-[520px]">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b text-left text-xs uppercase text-muted-foreground">
            <th className="px-2 py-2">Name</th>
            <th className="px-2 py-2">Action</th>
            <th className="px-2 py-2">Severity</th>
            <th className="px-2 py-2">Priority</th>
            <th className="px-2 py-2">Enabled</th>
            {showOrigin && <th className="px-2 py-2">Type</th>}
            <th className="px-2 py-2">Updated</th>
            <th className="px-2 py-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rules.map((rule) => {
            const global = isGlobalRule(rule);
            const canToggleGlobal = global && Boolean(rule.stable_key);
            return (
              <tr
                className={cn(
                  "border-b align-top",
                  !rule.enabled && "bg-muted/20"
                )}
                key={rule.id}
              >
                <td className="px-2 py-2">
                  <p className="font-medium">{rule.name}</p>
                  <p className="text-xs text-muted-foreground">{rule.stable_key ?? "-"}</p>
                </td>
                <td className="px-2 py-2">
                  <Badge>{rule.action}</Badge>
                </td>
                <td className="px-2 py-2">{rule.severity ?? "-"}</td>
                <td className="px-2 py-2">{rule.priority ?? "-"}</td>
                <td className="px-2 py-2">
                  <label className="inline-flex items-center gap-2">
                    <input
                      checked={rule.enabled}
                      disabled={!allowToggle || (global && !canToggleGlobal)}
                      onChange={(event) => onToggleEnabled(rule, event.target.checked)}
                      type="checkbox"
                    />
                    <Badge
                      className={
                        rule.enabled
                          ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                          : "border-slate-300 bg-slate-100 text-slate-700"
                      }
                    >
                      {rule.enabled ? "Enabled" : "Disabled"}
                    </Badge>
                  </label>
                </td>
                {showOrigin && (
                  <td className="px-2 py-2">
                    <Badge
                      className={
                        global
                          ? "bg-muted text-muted-foreground"
                          : "border-dashed text-muted-foreground"
                      }
                    >
                      {global ? "Global" : "Custom"}
                    </Badge>
                  </td>
                )}
                <td className="px-2 py-2 text-xs text-muted-foreground">
                  {formatDateTime(rule.updated_at)}
                </td>
                <td className="px-2 py-2">
                  <div className="flex min-w-[96px] flex-col gap-2">
                    {allowEdit ? (
                      <Button
                        className="h-8 justify-center whitespace-nowrap"
                        disabled={global}
                        onClick={() => onEditRule(rule)}
                        size="sm"
                        type="button"
                        variant="outline"
                      >
                        Edit
                      </Button>
                    ) : (
                      <Button
                        className="h-8 justify-center whitespace-nowrap"
                        disabled
                        size="sm"
                        type="button"
                        variant="outline"
                      >
                        View
                      </Button>
                    )}
                    {allowDelete ? (
                      <Button
                        className="h-8 justify-center whitespace-nowrap"
                        disabled={global || rule.can_soft_delete === false}
                        onClick={() => onDeleteRule(rule)}
                        size="sm"
                        type="button"
                        variant="outline"
                      >
                        Delete
                      </Button>
                    ) : (
                      <Button
                        className="h-8 justify-center whitespace-nowrap"
                        disabled
                        size="sm"
                        type="button"
                        variant="outline"
                      >
                        Read only
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </ScrollArea>
  );
}
