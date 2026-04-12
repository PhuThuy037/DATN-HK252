import {
  FormEvent,
  type ReactNode,
  useEffect,
  useMemo,
  useState,
} from "react";
import { Eye, Pencil, ShieldCheck, ShieldEllipsis, ShieldX, Trash2 } from "lucide-react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppButton } from "@/shared/ui/app-button";
import { AppLoadingState } from "@/shared/ui/app-loading-state";
import { AppModal } from "@/shared/ui/app-modal";
import { AppPageHeader } from "@/shared/ui/app-page-header";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { Card } from "@/shared/ui/card";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";
import { EmptyState } from "@/shared/ui/empty-state";
import { cn } from "@/shared/lib/utils";
import { StatusBadge } from "@/shared/ui/status-badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import { TechnicalDetailsAccordion } from "@/shared/ui/technical-details-accordion";
import { Textarea } from "@/shared/ui/textarea";
import { toast } from "@/shared/ui/use-toast";
import { RuleForm } from "@/features/rules/components/RuleForm";
import {
  useCreateRule,
  useDebugEvaluate,
  useDeleteRule,
  useEffectiveRules,
  useRuleDetail,
  useRuleChangeLogs,
  useRules,
  useToggleGlobalRule,
  useUpdateRule,
} from "@/features/rules/hooks";
import { useRuleSetStore } from "@/features/rules/store/ruleSetStore";
import type {
  CreateRuleRequest,
  CreateRuleWithContextRequest,
  DebugEvaluateResponse,
  EffectiveRule,
  Rule,
  RuleChangeLog,
  RuleDebugMatch,
  UpdateRuleRequest,
  UpdateRuleWithContextRequest,
} from "@/features/rules/types";

type RulesPageLocationState = {
  highlightRuleId?: string;
  openEditForRuleId?: string;
  source?: string;
};

type RulesTab = "my-rules" | "global-rules" | "effective-rules" | "change-logs" | "debug";
type StatusTone = "primary" | "success" | "warning" | "danger" | "muted";
const RULES_PAGE_LIMIT = 20;

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

function formatRuleTypeLabel(global: boolean) {
  return global ? "Global" : "Custom";
}

function formatSeverityLabel(value?: string | null) {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (!normalized) {
    return "Unknown";
  }
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function formatScopeLabel(value?: string | null) {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (!normalized) {
    return "Unknown";
  }
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function formatMatchModeLabel(value?: string | null) {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (!normalized) {
    return "Strict keyword";
  }
  if (normalized === "keyword_plus_semantic") {
    return "Keyword + semantic";
  }
  return "Strict keyword";
}

function getActionTone(action?: string | null): StatusTone {
  switch (String(action ?? "").trim().toLowerCase()) {
    case "allow":
      return "success";
    case "mask":
      return "warning";
    case "block":
      return "danger";
    case "warn":
      return "primary";
    default:
      return "muted";
  }
}

function getSeverityTone(severity?: string | null): StatusTone {
  switch (String(severity ?? "").trim().toLowerCase()) {
    case "high":
      return "danger";
    case "medium":
      return "warning";
    case "low":
      return "success";
    default:
      return "muted";
  }
}

function getRuleTypeTone(global: boolean): StatusTone {
  return global ? "primary" : "muted";
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
  footer,
  requireExplicitClose = false,
}: {
  title: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  requireExplicitClose?: boolean;
}) {
  return (
    <AppModal
      closeOnEscape={!requireExplicitClose}
      closeOnOverlayClick={!requireExplicitClose}
      footer={footer}
      onClose={onClose}
      open={open}
      size="xl"
      title={title}
    >
      {children}
    </AppModal>
  );
}

function RuleEnabledControl({
  enabled,
  disabled,
  onToggle,
}: {
  enabled: boolean;
  disabled?: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <StatusBadge status={enabled ? "enabled" : "disabled"} />
      <AppButton
        className="h-8 rounded-full px-3 text-xs"
        disabled={disabled}
        onClick={onToggle}
        size="sm"
        type="button"
        variant="secondary"
      >
        {enabled ? "Disable" : "Enable"}
      </AppButton>
    </div>
  );
}

function getRuleActionIcon(action?: string | null) {
  const normalized = String(action ?? "").trim().toLowerCase();
  if (normalized === "allow") {
    return <ShieldCheck className="h-4 w-4 text-success" />;
  }
  if (normalized === "mask") {
    return <ShieldEllipsis className="h-4 w-4 text-warning" />;
  }
  if (normalized === "block") {
    return <ShieldX className="h-4 w-4 text-danger" />;
  }
  return null;
}

function RuleDetailsPanel({ rule }: { rule: Rule }) {
  const global = isGlobalRule(rule);
  const linkedContextTerms = (rule.context_terms ?? []).filter((term) =>
    String(term.term ?? "").trim()
  );

  return (
    <div className="space-y-4">
      <AppSectionCard
        description={rule.description?.trim() || "No description provided for this rule."}
        title={rule.name}
      >
        <div className="flex flex-wrap gap-2">
          <StatusBadge label={formatActionLabel(rule.action)} tone={getActionTone(rule.action)} />
          <StatusBadge label={formatSeverityLabel(rule.severity)} tone={getSeverityTone(rule.severity)} />
          <StatusBadge status={rule.enabled ? "enabled" : "disabled"} />
          <StatusBadge label={formatRuleTypeLabel(global)} tone={getRuleTypeTone(global)} />
          <StatusBadge label={formatScopeLabel(rule.scope)} tone="muted" />
        </div>

        <div className="grid gap-3 text-sm text-muted-foreground md:grid-cols-2">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide">Stable key</p>
            <p className="mt-1 break-all text-foreground">{rule.stable_key ?? "-"}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide">Priority</p>
            <p className="mt-1 text-foreground">{rule.priority ?? "-"}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide">RAG mode</p>
            <p className="mt-1 text-foreground">{rule.rag_mode ?? "-"}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide">Match mode</p>
            <p className="mt-1 text-foreground">{formatMatchModeLabel(rule.match_mode)}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide">Updated</p>
            <p className="mt-1 text-foreground">{formatDateTime(rule.updated_at)}</p>
          </div>
        </div>
      </AppSectionCard>

      <AppSectionCard
        description="Semantic support material linked directly to this rule."
        title="Linked context terms"
      >
        {linkedContextTerms.length === 0 ? (
          <p className="text-sm text-muted-foreground">No linked context terms saved for this rule.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {linkedContextTerms.map((term, index) => (
              <StatusBadge
                key={term.id ?? `${term.term}-${index}`}
                label={term.term}
                tone="muted"
              />
            ))}
          </div>
        )}
      </AppSectionCard>

      <TechnicalDetailsAccordion
        sections={[
          {
            title: "Conditions JSON",
            data: rule.conditions ?? null,
          },
          {
            title: "Rule metadata",
            data: {
              id: rule.id,
              stable_key: rule.stable_key,
              scope: rule.scope,
              action: rule.action,
              severity: rule.severity,
              priority: rule.priority,
              match_mode: rule.match_mode,
              rag_mode: rule.rag_mode,
              enabled: rule.enabled,
              context_terms: linkedContextTerms,
              origin: rule.origin,
              created_at: rule.created_at,
              updated_at: rule.updated_at,
            },
          },
        ]}
        title="Technical details"
      />
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

const RULE_CHANGE_FIELD_LABELS: Record<string, string> = {
  action: "Action",
  conditions: "Conditions",
  conditions_version: "Conditions version",
  description: "Description",
  enabled: "Enabled",
  is_deleted: "Deleted",
  name: "Name",
  priority: "Priority",
  rag_mode: "RAG mode",
  scope: "Scope",
  severity: "Severity",
  stable_key: "Stable key",
};

const RULE_CHANGE_HIGHLIGHT_FIELDS = [
  "name",
  "stable_key",
  "action",
  "scope",
  "severity",
  "priority",
  "rag_mode",
  "enabled",
  "is_deleted",
  "description",
];

function formatRuleChangeActionLabel(action?: string | null) {
  switch (String(action ?? "").trim().toLowerCase()) {
    case "rule.create_custom":
      return "Created custom rule";
    case "rule.update":
      return "Updated rule";
    case "rule.delete":
      return "Deleted rule";
    case "rule.toggle_global_enabled":
      return "Toggled global rule";
    default:
      return formatActionLabel(action);
  }
}

function getRuleChangeActionTone(action?: string | null): StatusTone {
  switch (String(action ?? "").trim().toLowerCase()) {
    case "rule.create_custom":
      return "success";
    case "rule.update":
      return "primary";
    case "rule.delete":
      return "danger";
    case "rule.toggle_global_enabled":
      return "warning";
    default:
      return "muted";
  }
}

function getRuleChangeFieldTone(field?: string | null): StatusTone {
  switch (String(field ?? "").trim().toLowerCase()) {
    case "action":
      return "primary";
    case "severity":
    case "enabled":
      return "warning";
    case "is_deleted":
      return "danger";
    case "scope":
    case "priority":
    case "rag_mode":
      return "primary";
    default:
      return "muted";
  }
}

function getRuleChangeSnapshot(log: RuleChangeLog) {
  return asRecord(log.after_json) ?? asRecord(log.before_json);
}

function formatRuleChangeFieldLabel(field?: string | null) {
  const normalized = String(field ?? "").trim();
  if (!normalized) {
    return "Unknown field";
  }
  return RULE_CHANGE_FIELD_LABELS[normalized] ?? normalized.split("_").join(" ");
}

function formatRuleChangeValue(field: string, value: unknown) {
  if (field === "conditions") {
    return value ? "updated" : "none";
  }

  if (field === "action") {
    return formatActionLabel(value as string | null);
  }

  if (field === "enabled" || field === "is_deleted") {
    return formatSummaryValue(value, "no");
  }

  return formatSummaryValue(value);
}

function getRuleChangeHighlights(log: RuleChangeLog) {
  const before = asRecord(log.before_json);
  const after = asRecord(log.after_json);
  const changedFields = Array.from(new Set(log.changed_fields ?? []));
  const highlights: Array<{ field: string; before: string; after: string }> = [];

  for (const field of RULE_CHANGE_HIGHLIGHT_FIELDS) {
    if (!changedFields.includes(field)) {
      continue;
    }

    const beforeValue = formatRuleChangeValue(field, before?.[field]);
    const afterValue = formatRuleChangeValue(field, after?.[field]);

    if (beforeValue === afterValue) {
      continue;
    }

    highlights.push({
      field,
      before: beforeValue,
      after: afterValue,
    });
  }

  if (changedFields.includes("conditions")) {
    highlights.push({
      field: "conditions",
      before: before ? "previous logic" : "none",
      after: after ? "updated logic" : "removed",
    });
  }

  return highlights.slice(0, 6);
}

function getRuleChangeSummary(log: RuleChangeLog) {
  const snapshot = getRuleChangeSnapshot(log);
  const action = String(log.action ?? "").trim().toLowerCase();
  const enabledLabel = snapshot?.enabled === false ? "disabled" : "enabled";
  const actionLabel = formatActionLabel(snapshot?.action as string | null).toLowerCase();
  const scopeLabel = formatSummaryValue(snapshot?.scope, "current scope").toLowerCase();
  const changedCount = log.changed_fields?.length ?? 0;

  switch (action) {
    case "rule.create_custom":
      return `Created a ${enabledLabel} ${actionLabel} rule for ${scopeLabel}.`;
    case "rule.delete":
      return "Removed this custom rule from runtime and marked it as deleted.";
    case "rule.toggle_global_enabled":
      return snapshot?.enabled === false
        ? "Disabled this global rule for the current workspace."
        : "Enabled this global rule for the current workspace.";
    case "rule.update":
      return changedCount > 0
        ? `Updated ${changedCount} field${changedCount === 1 ? "" : "s"} on this rule.`
        : "Updated this rule.";
    default:
      return "Rule change recorded.";
  }
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
      <AppSectionCard
        actions={
          <div className="flex items-center gap-2">
            {getRuleActionIcon(result.final_action)}
            <StatusBadge
              label={formatActionLabel(result.final_action)}
              tone={getActionTone(result.final_action)}
            />
          </div>
        }
        description={getDebugSummaryExplanation(result, primaryMatch)}
        title="Summary"
      >
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
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
      </AppSectionCard>

      <AppSectionCard
        actions={
          <StatusBadge
            label={`${matchedRules.length} ${matchedRules.length === 1 ? "rule" : "rules"}`}
            tone="muted"
          />
        }
        description="Rules are sorted by priority, with the most relevant match highlighted first."
        title="Matched Rules"
      >
        {matchedRules.length === 0 ? (
          <EmptyState
            description="This input followed the default decision path for the current rule set."
            title="No matched rules"
          />
        ) : (
          <div className="space-y-3">
            {matchedRules.map((rule, index) => {
              const isPrimary = isSameDebugMatch(rule, primaryMatch) || (!primaryMatch && index === 0);
              return (
                <div
                  className={cn(
                    "rounded-2xl border border-border/80 bg-background p-4",
                    isPrimary && "ring-2 ring-primary/25 ring-offset-2"
                  )}
                  key={rule.rule_id ?? rule.stable_key ?? `${rule.name ?? "rule"}-${index}`}
                >
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="text-sm font-semibold text-foreground">
                          {rule.name?.trim() || "Unnamed rule"}
                        </h4>
                        {isPrimary ? <StatusBadge label="Main match" tone="primary" /> : null}
                        <StatusBadge
                          label={formatActionLabel(rule.action)}
                          tone={getActionTone(rule.action)}
                        />
                      </div>
                      <p className="break-all text-xs text-muted-foreground">
                        {rule.stable_key?.trim() || "No stable key"}
                      </p>
                    </div>

                    <div className="grid gap-1 text-xs text-muted-foreground md:text-right">
                      <span>Priority: {rule.priority ?? "-"}</span>
                      <span>Rule ID: {rule.rule_id ?? "-"}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </AppSectionCard>

      <TechnicalDetailsAccordion
        description="Raw debug payload is preserved here for deeper inspection."
        sections={[
          {
            title: "Raw matched rules JSON",
            data: result.matched_rules ?? [],
          },
          {
            title: "Raw signals JSON",
            data: result.signals ?? {},
          },
          {
            title: "Extra engine/debug output",
            data: hasExtraDebugOutput
              ? extraDebugOutput
              : "No additional engine debug fields were returned for this run.",
          },
        ]}
        title="Technical details"
      />
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
  const highlightedRuleId = locationState?.highlightRuleId?.trim() ?? "";
  const [createOpen, setCreateOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<Rule | null>(null);
  const [viewingRule, setViewingRule] = useState<Rule | null>(null);
  const [rulePendingDelete, setRulePendingDelete] = useState<Rule | null>(null);
  const createRuleFormId = "create-rule-form";
  const editRuleFormId = editingRule ? `edit-rule-form-${editingRule.id}` : "edit-rule-form";
  const editingRuleDetailQuery = useRuleDetail(editingRule?.id);
  const viewingRuleDetailQuery = useRuleDetail(viewingRule?.id);
  const [debugContent, setDebugContent] = useState("");
  const [activeTab, setActiveTab] = useState<RulesTab>("my-rules");
  const [deletedRules, setDeletedRules] = useState<Array<{ id: string; stableKey?: string | null }>>([]);

  const currentRuleSetId = useRuleSetStore((state) => state.currentRuleSetId);
  const currentRuleSet = useRuleSetStore((state) => state.currentRuleSet);
  const isRuleSetResolved = useRuleSetStore((state) => state.isRuleSetResolved);

  const myRulesQuery = useRules(currentRuleSetId ?? undefined, {
    tab: "my",
    limit: RULES_PAGE_LIMIT,
  });
  const globalRulesQuery = useRules(currentRuleSetId ?? undefined, {
    tab: "global",
    limit: RULES_PAGE_LIMIT,
  });
  const effectiveRulesQuery = useEffectiveRules({ limit: RULES_PAGE_LIMIT });
  const changeLogsQuery = useRuleChangeLogs(currentRuleSetId ?? undefined, {
    limit: RULES_PAGE_LIMIT,
  });
  const createRuleMutation = useCreateRule(currentRuleSetId ?? undefined);
  const updateRuleMutation = useUpdateRule(currentRuleSetId ?? undefined);
  const deleteRuleMutation = useDeleteRule(currentRuleSetId ?? undefined);
  const toggleGlobalRuleMutation = useToggleGlobalRule(currentRuleSetId ?? undefined);
  const debugEvaluateMutation = useDebugEvaluate();

  useEffect(() => {
    setDeletedRules([]);
  }, [currentRuleSetId]);

  const deletedRuleIds = useMemo(() => new Set(deletedRules.map((rule) => rule.id)), [deletedRules]);
  const deletedStableKeys = useMemo(
    () => new Set(deletedRules.map((rule) => rule.stableKey).filter(Boolean)),
    [deletedRules]
  );

  const myRulesRaw = useMemo(
    () => (myRulesQuery.data?.pages ?? []).flatMap((page) => page.items ?? []),
    [myRulesQuery.data]
  );
  const globalRules = useMemo(
    () => (globalRulesQuery.data?.pages ?? []).flatMap((page) => page.items ?? []),
    [globalRulesQuery.data]
  );
  const myRules = useMemo(
    () => myRulesRaw.filter((rule) => !deletedRuleIds.has(rule.id)),
    [deletedRuleIds, myRulesRaw]
  );
  const rules = useMemo(() => [...myRules, ...globalRules], [globalRules, myRules]);
  const changeLogs = useMemo(
    () => (changeLogsQuery.data?.pages ?? []).flatMap((page) => page.items ?? []),
    [changeLogsQuery.data]
  );
  const effectiveRules = useMemo(
    () =>
      ((effectiveRulesQuery.data?.pages ?? []).flatMap((page) => page.items ?? [])).filter((rule) => {
        const candidateId = rule.rule_id ?? rule.id ?? "";
        if (candidateId && deletedRuleIds.has(candidateId)) {
          return false;
        }
        if (rule.stable_key && deletedStableKeys.has(rule.stable_key)) {
          return false;
        }
        return true;
      }),
    [deletedRuleIds, deletedStableKeys, effectiveRulesQuery.data]
  );

  const myRulesTotal = myRulesQuery.data?.pages[0]?.total ?? myRules.length;
  const globalRulesTotal = globalRulesQuery.data?.pages[0]?.total ?? globalRules.length;
  const effectiveRulesTotal = effectiveRulesQuery.data?.pages[0]?.total ?? effectiveRules.length;
  const changeLogsTotal = changeLogsQuery.data?.pages[0]?.total ?? changeLogs.length;

  useEffect(() => {
    const targetRuleId = editRuleIdFromQuery || locationState?.openEditForRuleId?.trim() || "";
    if (!targetRuleId) {
      return;
    }

    const targetRule = rules.find((rule) => rule.id === targetRuleId);
    if (targetRule) {
      setActiveTab(isGlobalRule(targetRule) ? "global-rules" : "my-rules");
      setEditingRule(targetRule);
      navigate(location.pathname, { replace: true });
      return;
    }

    if (
      myRulesQuery.isLoading ||
      globalRulesQuery.isLoading ||
      myRulesQuery.isFetchingNextPage ||
      globalRulesQuery.isFetchingNextPage ||
      myRulesQuery.hasNextPage ||
      globalRulesQuery.hasNextPage
    ) {
      return;
    }

    if (rules.length > 0) {
      toast({
        title: "Rule not found",
        description: "Unable to open the requested rule for editing.",
        variant: "destructive",
      });
      navigate(location.pathname, { replace: true });
    } else {
      return;
    }
  }, [
    editRuleIdFromQuery,
    globalRulesQuery.hasNextPage,
    globalRulesQuery.isFetchingNextPage,
    globalRulesQuery.isLoading,
    location.pathname,
    locationState?.openEditForRuleId,
    myRulesQuery.hasNextPage,
    myRulesQuery.isFetchingNextPage,
    myRulesQuery.isLoading,
    navigate,
    rules,
  ]);

  const handleCreateRule = async (
    payload:
      | CreateRuleRequest
      | CreateRuleWithContextRequest
      | UpdateRuleRequest
      | UpdateRuleWithContextRequest
  ) => {
    try {
      await createRuleMutation.mutateAsync(
        payload as CreateRuleRequest | CreateRuleWithContextRequest
      );
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

  const handleUpdateRule = async (
    payload:
      | CreateRuleRequest
      | CreateRuleWithContextRequest
      | UpdateRuleRequest
      | UpdateRuleWithContextRequest
  ) => {
    if (!editingRule) {
      return;
    }
    try {
      await updateRuleMutation.mutateAsync({
        ruleId: editingRule.id,
        payload: payload as UpdateRuleRequest | UpdateRuleWithContextRequest,
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
      setDeletedRules((prev) => [
        ...prev.filter((item) => item.id !== rulePendingDelete.id),
        { id: rulePendingDelete.id, stableKey: rulePendingDelete.stable_key },
      ]);
      if (editingRule?.id === rulePendingDelete.id) {
        setEditingRule(null);
      }
      if (viewingRule?.id === rulePendingDelete.id) {
        setViewingRule(null);
      }
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
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4">
        <AppPageHeader
          actions={
            activeTab === "my-rules" ? (
              <AppButton onClick={() => setCreateOpen(true)} type="button">
                New Rule
              </AppButton>
            ) : undefined
          }
          meta={`Workspace: ${currentRuleSet?.name ?? "Current rule set"}`}
          subtitle="Manage custom rules, global overrides, runtime-effective rules, change history, and debug evaluation from one consistent admin surface."
          title="Rules Management"
        />

        <Tabs onValueChange={(value) => setActiveTab(value as RulesTab)} value={activeTab}>
          <TabsList className="flex flex-wrap">
            <TabsTrigger value="my-rules">My Rules</TabsTrigger>
            <TabsTrigger value="global-rules">Global Rules</TabsTrigger>
            <TabsTrigger value="effective-rules">Effective Rules</TabsTrigger>
            <TabsTrigger value="change-logs">Change Logs</TabsTrigger>
            <TabsTrigger value="debug">Debug Evaluate</TabsTrigger>
          </TabsList>

          <TabsContent value="my-rules">
            <AppSectionCard
              actions={
                <StatusBadge
                  label={`${myRulesTotal} ${myRulesTotal === 1 ? "rule" : "rules"}`}
                  tone="muted"
                />
              }
              description="Custom rules owned by the current workspace. Use the badges to scan action, severity, status, and rule type quickly."
              title="My Rules"
            >
              <RuleTable
                allowDelete
                allowEdit
                allowToggle
                emptyDescription="Create your first custom rule to start tailoring the workspace policy."
                emptyTitle="No custom rules yet"
                highlightRuleId={highlightedRuleId}
                isBusy={
                  updateRuleMutation.isPending ||
                  toggleGlobalRuleMutation.isPending ||
                  deleteRuleMutation.isPending
                }
                isError={myRulesQuery.isError}
                isLoading={myRulesQuery.isLoading}
                isLoadingMore={myRulesQuery.isFetchingNextPage}
                canLoadMore={Boolean(myRulesQuery.hasNextPage)}
                onLoadMore={() => void myRulesQuery.fetchNextPage()}
                onDeleteRule={handleRequestDeleteRule}
                onEditRule={setEditingRule}
                onToggleEnabled={handleToggleEnabled}
                onViewRule={setViewingRule}
                rules={myRules}
              />
            </AppSectionCard>
          </TabsContent>

          <TabsContent value="global-rules">
            <AppSectionCard
              actions={
                <StatusBadge
                  label={`${globalRulesTotal} ${globalRulesTotal === 1 ? "rule" : "rules"}`}
                  tone="muted"
                />
              }
              description="Global rules are visible here with per-workspace enable and disable control where supported."
              title="Global Rules"
            >
              <RuleTable
                allowDelete={false}
                allowEdit={false}
                allowToggle
                emptyDescription="Global baseline rules will appear here when available to the workspace."
                emptyTitle="No global rules available"
                highlightRuleId={highlightedRuleId}
                isBusy={updateRuleMutation.isPending || toggleGlobalRuleMutation.isPending}
                isError={globalRulesQuery.isError}
                isLoading={globalRulesQuery.isLoading}
                isLoadingMore={globalRulesQuery.isFetchingNextPage}
                canLoadMore={Boolean(globalRulesQuery.hasNextPage)}
                onLoadMore={() => void globalRulesQuery.fetchNextPage()}
                onDeleteRule={handleRequestDeleteRule}
                onEditRule={setEditingRule}
                onToggleEnabled={handleToggleEnabled}
                onViewRule={setViewingRule}
                rules={globalRules}
              />
            </AppSectionCard>
          </TabsContent>

          <TabsContent value="effective-rules">
            <AppSectionCard
              actions={
                <StatusBadge
                  label={`${effectiveRulesTotal} ${effectiveRulesTotal === 1 ? "rule" : "rules"}`}
                  tone="muted"
                />
              }
              description="These are the runtime-effective rules after custom rules and global overrides are combined."
              title="Effective Rules"
            >
              {effectiveRulesQuery.isLoading ? (
                <AppLoadingState
                  compact
                  description="Loading the runtime rule set used for evaluation."
                  title="Loading effective rules"
                />
              ) : effectiveRulesQuery.isError ? (
                <AppAlert
                  description="Failed to load effective rules."
                  title="Effective rules unavailable"
                  variant="error"
                />
              ) : effectiveRules.length === 0 ? (
                <EmptyState
                  description="No effective rules were returned for the current workspace."
                  title="No effective rules found"
                />
              ) : (
                <div className="space-y-3">
                  {effectiveRules.map((rule) => (
                    <EffectiveRuleCard
                      key={rule.id ?? rule.rule_id ?? rule.stable_key ?? rule.name}
                      rule={rule}
                    />
                  ))}
                  {effectiveRulesQuery.hasNextPage ? (
                    <div className="flex justify-center pt-1">
                      <AppButton
                        disabled={effectiveRulesQuery.isFetchingNextPage}
                        onClick={() => void effectiveRulesQuery.fetchNextPage()}
                        type="button"
                        variant="secondary"
                      >
                        {effectiveRulesQuery.isFetchingNextPage ? "Loading..." : "Load more"}
                      </AppButton>
                    </div>
                  ) : null}
                </div>
              )}
            </AppSectionCard>
          </TabsContent>

          <TabsContent value="change-logs">
            <AppSectionCard
              actions={
                <StatusBadge
                  label={`${changeLogsTotal} log${changeLogsTotal === 1 ? "" : "s"}`}
                  tone="muted"
                />
              }
              description="Recent rule changes across the current workspace, with changed fields and key deltas highlighted first."
              title="Change Logs"
            >
              {changeLogsQuery.isLoading ? (
                <AppLoadingState
                  compact
                  description="Loading recent rule activity for this workspace."
                  title="Loading change logs"
                />
              ) : changeLogsQuery.isError ? (
                <AppAlert
                  description="Failed to load change logs."
                  title="Change logs unavailable"
                  variant="error"
                />
              ) : changeLogs.length === 0 ? (
                <EmptyState
                  description="Rule updates, deletes, and global toggles will appear here."
                  title="No change logs yet"
                />
              ) : (
                <div className="space-y-3">
                  {changeLogs.map((log, index) => (
                    <RuleChangeLogCard key={log.id ?? `${index}-${log.created_at}`} index={index} log={log} />
                  ))}
                  {changeLogsQuery.hasNextPage ? (
                    <div className="flex justify-center pt-1">
                      <AppButton
                        disabled={changeLogsQuery.isFetchingNextPage}
                        onClick={() => void changeLogsQuery.fetchNextPage()}
                        type="button"
                        variant="secondary"
                      >
                        {changeLogsQuery.isFetchingNextPage ? "Loading..." : "Load more"}
                      </AppButton>
                    </div>
                  ) : null}
                </div>
              )}
            </AppSectionCard>
          </TabsContent>

          <TabsContent value="debug">
            <AppSectionCard
              description="Quickly test text against the current rule set and inspect the resulting action and matched rules."
              title="Debug Evaluate"
            >
              <form className="space-y-3" onSubmit={handleEvaluate}>
                <Textarea
                  className="min-h-[140px]"
                  onChange={(event) => setDebugContent(event.target.value)}
                  placeholder="Paste or type content to evaluate against the current rule set."
                  value={debugContent}
                />
                <div className="flex justify-end">
                  <AppButton
                    disabled={debugEvaluateMutation.isPending || !debugContent.trim()}
                    type="submit"
                  >
                    {debugEvaluateMutation.isPending ? "Evaluating..." : "Evaluate"}
                  </AppButton>
                </div>
              </form>

              {debugEvaluateMutation.isError ? (
                <AppAlert
                  description="Failed to evaluate text."
                  title="Debug evaluate failed"
                  variant="error"
                />
              ) : null}

              {debugEvaluateMutation.data && <DebugEvaluateResult result={debugEvaluateMutation.data} />}
            </AppSectionCard>
          </TabsContent>
        </Tabs>
      </div>

      <RuleModal
        footer={
          <div className="flex justify-end gap-2">
            <AppButton onClick={() => setCreateOpen(false)} type="button" variant="secondary">
              Cancel
            </AppButton>
            <AppButton disabled={createRuleMutation.isPending} form={createRuleFormId} type="submit">
              {createRuleMutation.isPending ? "Saving..." : "Create Rule"}
            </AppButton>
          </div>
        }
        onClose={() => setCreateOpen(false)}
        open={createOpen}
        requireExplicitClose
        title="Create new rule"
      >
        <RuleForm
          formId={createRuleFormId}
          hideActions
          isSubmitting={createRuleMutation.isPending}
          mode="create"
          onCancel={() => setCreateOpen(false)}
          onSubmit={handleCreateRule}
        />
      </RuleModal>

      <RuleModal
        footer={
          <div className="flex justify-end gap-2">
            <AppButton onClick={() => setEditingRule(null)} type="button" variant="secondary">
              Cancel
            </AppButton>
            <AppButton
              disabled={
                updateRuleMutation.isPending ||
                editingRuleDetailQuery.isLoading ||
                editingRuleDetailQuery.isError
              }
              form={editRuleFormId}
              type="submit"
            >
              {updateRuleMutation.isPending ? "Saving..." : "Save Changes"}
            </AppButton>
          </div>
        }
        onClose={() => setEditingRule(null)}
        open={Boolean(editingRule)}
        requireExplicitClose
        title="Edit rule"
      >
        {editingRule ? (
          editingRuleDetailQuery.isLoading ? (
            <AppLoadingState
              compact
              description="Loading full rule detail before editing."
              title="Loading rule detail"
            />
          ) : editingRuleDetailQuery.isError ? (
            <AppAlert
              description="Failed to load full rule detail for editing."
              title="Rule detail unavailable"
              variant="error"
            />
          ) : (
            <RuleForm
              formId={editRuleFormId}
              hideActions
              initialRule={editingRuleDetailQuery.data ?? editingRule}
              isSubmitting={updateRuleMutation.isPending}
              mode="edit"
              onCancel={() => setEditingRule(null)}
              onSubmit={handleUpdateRule}
            />
          )
        ) : null}
      </RuleModal>

      <RuleModal onClose={() => setViewingRule(null)} open={Boolean(viewingRule)} title="Rule details">
        {viewingRule ? (
          viewingRuleDetailQuery.isLoading ? (
            <AppLoadingState
              compact
              description="Loading full rule detail."
              title="Loading rule detail"
            />
          ) : viewingRuleDetailQuery.isError ? (
            <AppAlert
              description="Failed to load full rule detail."
              title="Rule detail unavailable"
              variant="error"
            />
          ) : (
            <RuleDetailsPanel rule={viewingRuleDetailQuery.data ?? viewingRule} />
          )
        ) : null}
      </RuleModal>

      <ConfirmDialog
        confirmLabel={deleteRuleMutation.isPending ? "Deleting..." : "Delete rule"}
        confirmVariant="danger"
        description={
          rulePendingDelete
            ? `Delete "${rulePendingDelete.name}"? This action cannot be undone.`
            : undefined
        }
        isBusy={deleteRuleMutation.isPending}
        onClose={handleCancelDeleteRule}
        onConfirm={() => void handleConfirmDeleteRule()}
        open={Boolean(rulePendingDelete)}
        title="Delete rule?"
      />
    </section>
  );
}

function RuleTable({
  rules,
  isLoading,
  isError,
  canLoadMore,
  isLoadingMore,
  emptyTitle,
  emptyDescription,
  allowEdit,
  allowDelete,
  allowToggle,
  highlightRuleId,
  isBusy,
  onViewRule,
  onEditRule,
  onDeleteRule,
  onToggleEnabled,
  onLoadMore,
}: {
  rules: Rule[];
  isLoading: boolean;
  isError: boolean;
  canLoadMore?: boolean;
  isLoadingMore?: boolean;
  emptyTitle: string;
  emptyDescription: string;
  allowEdit: boolean;
  allowDelete: boolean;
  allowToggle: boolean;
  highlightRuleId?: string;
  isBusy?: boolean;
  onViewRule: (rule: Rule) => void;
  onEditRule: (rule: Rule) => void;
  onDeleteRule: (rule: Rule) => void;
  onToggleEnabled: (rule: Rule, enabled: boolean) => void;
  onLoadMore?: () => void;
}) {
  if (isLoading) {
    return (
      <AppLoadingState
        compact
        description="Loading rules for the current workspace."
        title="Loading rules"
      />
    );
  }

  if (isError) {
    return (
      <AppAlert
        description="We couldn't load rules for the current workspace."
        title="Rules unavailable"
        variant="error"
      />
    );
  }

  if (rules.length === 0) {
    return <EmptyState description={emptyDescription} title={emptyTitle} />;
  }

  return (
    <div className="grid gap-3">
      {rules.map((rule) => {
        const global = isGlobalRule(rule);
        const canToggle = allowToggle && (!global || Boolean(rule.stable_key));
        const canEdit = allowEdit && !global;
        const canDelete = allowDelete && !global && rule.can_soft_delete !== false;
        const isHighlighted = Boolean(highlightRuleId) && rule.id === highlightRuleId;

        return (
          <Card
            className={cn(
              "space-y-4 p-4 md:p-5",
              !rule.enabled && "bg-muted/35",
              isHighlighted && "ring-2 ring-primary/25 ring-offset-2"
            )}
            key={rule.id}
          >
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-base font-semibold text-foreground">{rule.name}</h3>
                  {getRuleActionIcon(rule.action)}
                </div>
                <div className="flex flex-wrap gap-2">
                  <StatusBadge label={formatActionLabel(rule.action)} tone={getActionTone(rule.action)} />
                  <StatusBadge label={formatSeverityLabel(rule.severity)} tone={getSeverityTone(rule.severity)} />
                  <StatusBadge status={rule.enabled ? "enabled" : "disabled"} />
                  <StatusBadge label={formatRuleTypeLabel(global)} tone={getRuleTypeTone(global)} />
                  <StatusBadge label={formatScopeLabel(rule.scope)} tone="muted" />
                </div>
                <p className="text-sm text-muted-foreground">
                  {rule.description?.trim() || "No description provided for this rule."}
                </p>
                <p className="break-all text-xs text-muted-foreground">
                  Stable key: {rule.stable_key?.trim() || "Not provided"}
                </p>
              </div>

              <div className="grid gap-3 text-sm text-muted-foreground sm:grid-cols-3 lg:min-w-[320px]">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide">Priority</p>
                  <p className="mt-1 text-foreground">{rule.priority ?? "-"}</p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide">Updated</p>
                  <p className="mt-1 text-foreground">{formatDateTime(rule.updated_at)}</p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide">Match mode</p>
                  <p className="mt-1 text-foreground">
                    {formatMatchModeLabel(rule.match_mode)}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide">RAG mode</p>
                  <p className="mt-1 text-foreground">{formatSummaryValue(rule.rag_mode, "-")}</p>
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-3 border-t border-border/70 pt-4 md:flex-row md:items-center md:justify-between">
              <div className="space-y-2">
                <RuleEnabledControl
                  disabled={isBusy || !canToggle}
                  enabled={Boolean(rule.enabled)}
                  onToggle={() => onToggleEnabled(rule, !rule.enabled)}
                />
                {!canToggle && global && !rule.stable_key ? (
                  <p className="text-xs text-muted-foreground">
                    Toggle is unavailable because this global rule is missing a stable key.
                  </p>
                ) : null}
              </div>

              <div className="flex flex-wrap items-center gap-2 md:justify-end">
                <AppButton
                  className="min-w-[88px] justify-center"
                  leadingIcon={<Eye className="h-4 w-4" />}
                  onClick={() => onViewRule(rule)}
                  size="sm"
                  type="button"
                  variant="secondary"
                >
                  View
                </AppButton>
                <AppButton
                  className="min-w-[88px] justify-center"
                  disabled={!canEdit || isBusy}
                  leadingIcon={<Pencil className="h-4 w-4" />}
                  onClick={() => onEditRule(rule)}
                  size="sm"
                  type="button"
                  variant="secondary"
                >
                  Edit
                </AppButton>
                <AppButton
                  className="min-w-[88px] justify-center"
                  disabled={!canDelete || isBusy}
                  leadingIcon={<Trash2 className="h-4 w-4" />}
                  onClick={() => onDeleteRule(rule)}
                  size="sm"
                  type="button"
                  variant="danger"
                >
                  Delete
                </AppButton>
              </div>
            </div>
          </Card>
        );
      })}
      {canLoadMore ? (
        <div className="flex justify-center pt-1">
          <AppButton
            disabled={isLoadingMore}
            onClick={() => onLoadMore?.()}
            type="button"
            variant="secondary"
          >
            {isLoadingMore ? "Loading..." : "Load more"}
          </AppButton>
        </div>
      ) : null}
    </div>
  );
}

function EffectiveRuleCard({ rule }: { rule: EffectiveRule }) {
  const global = String(rule.origin ?? "")
    .trim()
    .toLowerCase()
    .match(/global|override/) != null;

  return (
    <Card className="space-y-4 p-4 md:p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold text-foreground">{rule.name}</h3>
            {getRuleActionIcon(rule.action)}
            <StatusBadge label={formatActionLabel(rule.action)} tone={getActionTone(rule.action)} />
            <StatusBadge status={rule.enabled === false ? "disabled" : "enabled"} />
          </div>
          <p className="break-all text-xs text-muted-foreground">
            Stable key: {rule.stable_key?.trim() || "Not provided"}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <StatusBadge label={formatRuleTypeLabel(global)} tone={getRuleTypeTone(global)} />
          <StatusBadge label={formatSummaryValue(rule.origin, "Runtime")} tone="muted" />
        </div>
      </div>

      <div className="grid gap-3 text-sm text-muted-foreground sm:grid-cols-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide">Priority</p>
          <p className="mt-1 text-foreground">{rule.priority ?? "-"}</p>
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-wide">Rule ID</p>
          <p className="mt-1 break-all text-foreground">{rule.rule_id ?? rule.id ?? "-"}</p>
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-wide">Source</p>
          <p className="mt-1 text-foreground">{formatSummaryValue(rule.origin, "Runtime")}</p>
        </div>
      </div>
    </Card>
  );
}

function RuleChangeLogCard({ log, index }: { log: RuleChangeLog; index: number }) {
  const snapshot = getRuleChangeSnapshot(log);
  const highlights = getRuleChangeHighlights(log);
  const changedFields = Array.from(new Set(log.changed_fields ?? []));
  const ruleName = String(snapshot?.name ?? "").trim() || `Rule change ${index + 1}`;
  const stableKey = String(snapshot?.stable_key ?? "").trim();

  return (
    <Card className="space-y-4 p-4 md:p-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold text-foreground">{ruleName}</h3>
            <StatusBadge
              label={formatRuleChangeActionLabel(log.action)}
              tone={getRuleChangeActionTone(log.action)}
            />
          </div>
          <p className="text-sm text-muted-foreground">{getRuleChangeSummary(log)}</p>
          <p className="break-all text-xs text-muted-foreground">
            {stableKey ? `Stable key: ${stableKey}` : "Stable key unavailable"}
          </p>
        </div>

        <div className="grid gap-1 text-xs text-muted-foreground lg:text-right">
          <span>{formatDateTime(log.created_at)}</span>
          <span>Rule ID: {log.rule_id ?? "-"}</span>
          <span>Actor: {log.actor_user_id ?? "system"}</span>
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Changed fields
        </p>
        {changedFields.length === 0 ? (
          <p className="text-sm text-muted-foreground">No changed fields were recorded.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {changedFields.map((field) => (
              <StatusBadge
                key={field}
                label={formatRuleChangeFieldLabel(field)}
                tone={getRuleChangeFieldTone(field)}
              />
            ))}
          </div>
        )}
      </div>

      {highlights.length > 0 ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {highlights.map((highlight) => (
            <div className="rounded-xl border border-border/70 bg-background p-3" key={highlight.field}>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {formatRuleChangeFieldLabel(highlight.field)}
              </p>
              <p className="mt-2 text-xs text-muted-foreground">Before</p>
              <p className="text-sm font-medium text-foreground">{highlight.before}</p>
              <p className="mt-2 text-xs text-muted-foreground">After</p>
              <p className="text-sm font-medium text-foreground">{highlight.after}</p>
            </div>
          ))}
        </div>
      ) : null}

      {log.reason ? (
        <AppAlert description={log.reason} title="Reason" variant="info" />
      ) : null}

      <TechnicalDetailsAccordion
        sections={[
          {
            title: "Before snapshot",
            data: log.before_json ?? "No previous snapshot was recorded.",
          },
          {
            title: "After snapshot",
            data: log.after_json ?? "No updated snapshot was recorded.",
          },
          {
            title: "Change log metadata",
            data: {
              id: log.id,
              rule_id: log.rule_id,
              actor_user_id: log.actor_user_id,
              action: log.action,
              changed_fields: log.changed_fields,
              created_at: log.created_at,
            },
          },
        ]}
        title="Technical details"
      />
    </Card>
  );
}
