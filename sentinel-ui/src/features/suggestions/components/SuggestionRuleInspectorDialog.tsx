import { Info } from "lucide-react";
import type { RuleDetail } from "@/features/rules/types";
import type { SuggestionDraft } from "@/features/suggestions/types";
import {
  type DuplicateUiState,
  resolveDuplicateUiState,
} from "@/features/suggestions/components/duplicateUiState";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppButton } from "@/shared/ui/app-button";
import { AppLoadingState } from "@/shared/ui/app-loading-state";
import { AppModal } from "@/shared/ui/app-modal";
import { Badge } from "@/shared/ui/badge";
import { Card } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { cn } from "@/shared/lib/utils";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { StatusBadge } from "@/shared/ui/status-badge";
import { TechnicalDetailsAccordion } from "@/shared/ui/technical-details-accordion";

type RuleInspectorMode = "view" | "compare";

type CompareContextTerm = {
  entity_type: string;
  term: string;
  lang: string;
  weight: number;
  enabled: boolean;
};

type RuleSummary = {
  title: string;
  stableKey?: string;
  description?: string | null;
  action: string;
  scope: string;
  severity: string;
  priority: number;
  ragMode: string;
  enabled: boolean;
  conditions: unknown;
  contextTerms: CompareContextTerm[];
  createdAt?: string;
  updatedAt?: string;
};

type ConditionDescription = {
  text: string;
  badges: string[];
  tokens: string[];
};

type ConditionViewModel = {
  title: string;
  bullets: string[];
  badges: string[];
  tokens: string[];
};

type ListDiff = {
  added: string[];
  removed: string[];
  unchanged: string[];
};

type CompareFieldDiff = {
  action: boolean;
  scope: boolean;
  severity: boolean;
  priority: boolean;
  ragMode: boolean;
  enabled: boolean;
  conditions: boolean;
  contextTerms: boolean;
};

type CompareViewModel = {
  identical: boolean;
  changedFields: string[];
  matchedFields: string[];
  fieldDiff: CompareFieldDiff;
  conditionsDiff: ListDiff;
  contextTermsDiff: ListDiff;
  contextTermsIdentical: boolean;
};

type SuggestionRuleInspectorDialogProps = {
  open: boolean;
  mode: RuleInspectorMode;
  candidateName?: string;
  candidateOrigin?: string | null;
  existingRule: RuleDetail | null;
  draft: SuggestionDraft;
  isLoading: boolean;
  errorMessage?: string | null;
  duplicateDecision?: string | null;
  candidateSimilarity?: number | null;
  onRetry?: () => void;
  onEditExistingRule?: () => void;
  onContinueAnyway?: () => void;
  onClose: () => void;
};

function toTitleCase(value: string) {
  return String(value || "")
    .split("_")
    .join(" ")
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}

function toSentenceCase(value: string) {
  const text = String(value || "").trim();
  if (!text) {
    return text;
  }
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function toPrettyJson(value: unknown) {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return String(value ?? "");
  }
}

function toMatchPercent(similarity?: number | null) {
  if (typeof similarity !== "number" || Number.isNaN(similarity)) {
    return null;
  }
  return Math.max(0, Math.min(100, Math.round(similarity * 100)));
}

function isGlobalCandidateOrigin(origin?: string | null) {
  const value = String(origin ?? "").trim().toLowerCase();
  return value.includes("global");
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item ?? "").trim()).filter(Boolean);
}

function dedupeStrings(values: string[]) {
  return Array.from(new Set(values.filter((value) => value.trim().length > 0)));
}

function quote(value: string) {
  return `"${value}"`;
}

function formatFieldLabel(field: string) {
  const normalized = String(field || "").trim().toLowerCase();
  if (!normalized) {
    return "Signal";
  }
  if (normalized === "context_keywords") {
    return "Context keyword";
  }
  return toTitleCase(normalized);
}

function normalizeExistingRule(rule: RuleDetail): RuleSummary {
  return {
    title: rule.name || "Existing rule",
    stableKey: rule.stable_key || "",
    description: rule.description,
    action: String(rule.action || ""),
    scope: String(rule.scope || ""),
    severity: String(rule.severity || ""),
    priority: Number(rule.priority ?? 0),
    ragMode: String(rule.rag_mode || ""),
    enabled: Boolean(rule.enabled),
    conditions: rule.conditions,
    contextTerms: (rule.context_terms ?? []).map((term) => ({
      entity_type: String(term.entity_type || ""),
      term: String(term.term || ""),
      lang: String(term.lang || ""),
      weight: Number(term.weight ?? 0),
      enabled: Boolean(term.enabled),
    })),
    createdAt: rule.created_at,
    updatedAt: rule.updated_at,
  };
}

function normalizeDraftRule(draft: SuggestionDraft): RuleSummary {
  const rule = draft.rule;
  return {
    title: String(rule.name || "Draft suggestion"),
    stableKey: String(rule.stable_key || ""),
    description: rule.description,
    action: String(rule.action || ""),
    scope: String(rule.scope || ""),
    severity: String(rule.severity || ""),
    priority: Number(rule.priority ?? 0),
    ragMode: String(rule.rag_mode || ""),
    enabled: Boolean(rule.enabled),
    conditions: rule.conditions,
    contextTerms: (draft.context_terms ?? []).map((term) => ({
      entity_type: String(term.entity_type || ""),
      term: String(term.term || ""),
      lang: String(term.lang || ""),
      weight: Number(term.weight ?? 0),
      enabled: Boolean(term.enabled),
    })),
  };
}

function describeSignalCondition(signal: Record<string, unknown>): ConditionDescription {
  const field = String(signal.field ?? "").trim();
  const fieldKey = field.toLowerCase() || "signal";
  const fieldLabel = formatFieldLabel(field);
  const anyOf = asStringArray(signal.any_of);
  const allOf = asStringArray(signal.all_of);
  const containsValue = signal.contains;
  const equalsValue = signal.equals;

  if (anyOf.length > 0) {
    const text =
      field === "context_keywords"
        ? anyOf.length === 1
          ? `context keyword contains ${quote(anyOf[0])}`
          : `context keyword contains any of ${anyOf.map(quote).join(", ")}`
        : `${fieldLabel} matches any of ${anyOf.map(quote).join(", ")}`;

    const badges = anyOf.map((value) =>
      field === "context_keywords" ? `Keyword: ${value}` : `${fieldLabel}: ${value}`
    );
    const tokens = anyOf.map((value) => `${fieldKey}:${value.toLowerCase()}`);
    return { text, badges, tokens };
  }

  if (allOf.length > 0) {
    const text =
      field === "context_keywords"
        ? `context keywords include all of ${allOf.map(quote).join(", ")}`
        : `${fieldLabel} matches all of ${allOf.map(quote).join(", ")}`;

    const badges = allOf.map((value) =>
      field === "context_keywords" ? `Keyword: ${value}` : `${fieldLabel}: ${value}`
    );
    const tokens = allOf.map((value) => `${fieldKey}:${value.toLowerCase()}`);
    return { text, badges, tokens };
  }

  if (typeof containsValue === "string" && containsValue.trim()) {
    const token = containsValue.trim();
    return {
      text:
        field === "context_keywords"
          ? `context keyword contains ${quote(token)}`
          : `${fieldLabel} contains ${quote(token)}`,
      badges: [field === "context_keywords" ? `Keyword: ${token}` : `${fieldLabel}: ${token}`],
      tokens: [`${fieldKey}:${token.toLowerCase()}`],
    };
  }

  if (
    (typeof equalsValue === "string" && equalsValue.trim()) ||
    typeof equalsValue === "number" ||
    typeof equalsValue === "boolean"
  ) {
    const token = String(equalsValue).trim();
    return {
      text: `${fieldLabel} equals ${quote(token)}`,
      badges: [`${fieldLabel}: ${token}`],
      tokens: [`${fieldKey}:${token.toLowerCase()}`],
    };
  }

  if (fieldLabel !== "Signal") {
    return {
      text: `${fieldLabel} condition is configured`,
      badges: [],
      tokens: [`${fieldKey}:configured`],
    };
  }

  return {
    text: "Custom signal condition is configured",
    badges: [],
    tokens: ["signal:configured"],
  };
}

function describeConditionNode(node: unknown): ConditionDescription {
  const record = asRecord(node);
  if (!record) {
    return {
      text: "Custom condition is configured",
      badges: [],
      tokens: ["condition:custom"],
    };
  }

  if (typeof record.entity_type === "string" && record.entity_type.trim()) {
    const entityType = record.entity_type.trim();
    return {
      text: `entity is ${entityType}`,
      badges: [`Entity: ${entityType}`],
      tokens: [`entity:${entityType.toLowerCase()}`],
    };
  }

  const signalNode = asRecord(record.signal);
  if (signalNode) {
    return describeSignalCondition(signalNode);
  }

  if (Array.isArray(record.any)) {
    const children = record.any
      .map((child) => describeConditionNode(child))
      .filter((child) => child.text.trim().length > 0);
    return {
      text: children.map((child) => child.text).join(" OR "),
      badges: children.flatMap((child) => child.badges),
      tokens: children.flatMap((child) => child.tokens),
    };
  }

  if (Array.isArray(record.all)) {
    const children = record.all
      .map((child) => describeConditionNode(child))
      .filter((child) => child.text.trim().length > 0);
    return {
      text: children.map((child) => child.text).join(" AND "),
      badges: children.flatMap((child) => child.badges),
      tokens: children.flatMap((child) => child.tokens),
    };
  }

  if (record.not) {
    const inner = describeConditionNode(record.not);
    return {
      text: `NOT (${inner.text || "custom condition"})`,
      badges: inner.badges,
      tokens: inner.tokens.map((token) => `not:${token}`),
    };
  }

  return {
    text: "Custom condition is configured",
    badges: [],
    tokens: ["condition:custom"],
  };
}

function buildConditionViewModel(conditions: unknown): ConditionViewModel {
  const root = asRecord(conditions);
  if (!root) {
    return {
      title: "This rule triggers when:",
      bullets: ["Custom condition is configured"],
      badges: [],
      tokens: ["condition:custom"],
    };
  }

  if (Array.isArray(root.any)) {
    const children = root.any.map((child) => describeConditionNode(child)).filter((child) => child.text);
    const bullets = children.map((child, index) =>
      index === 0 ? toSentenceCase(child.text) : `OR ${child.text}`
    );
    return {
      title: "Match ANY of:",
      bullets: bullets.length > 0 ? bullets : ["No conditions found"],
      badges: dedupeStrings(children.flatMap((child) => child.badges)),
      tokens: dedupeStrings(children.flatMap((child) => child.tokens)),
    };
  }

  if (Array.isArray(root.all)) {
    const children = root.all.map((child) => describeConditionNode(child)).filter((child) => child.text);
    const bullets = children.map((child, index) =>
      index === 0 ? toSentenceCase(child.text) : `AND ${child.text}`
    );
    return {
      title: "Match ALL of:",
      bullets: bullets.length > 0 ? bullets : ["No conditions found"],
      badges: dedupeStrings(children.flatMap((child) => child.badges)),
      tokens: dedupeStrings(children.flatMap((child) => child.tokens)),
    };
  }

  if (root.not) {
    const inner = describeConditionNode(root.not);
    return {
      title: "Match when NOT:",
      bullets: [inner.text ? toSentenceCase(inner.text) : "Custom condition is configured"],
      badges: dedupeStrings(inner.badges),
      tokens: dedupeStrings(inner.tokens),
    };
  }

  const single = describeConditionNode(root);
  return {
    title: "This rule triggers when:",
    bullets: [single.text ? toSentenceCase(single.text) : "Custom condition is configured"],
    badges: dedupeStrings(single.badges),
    tokens: dedupeStrings(single.tokens),
  };
}

function compactStableKey(stableKey: string | undefined) {
  const text = String(stableKey || "").trim();
  if (!text) {
    return "";
  }

  const parts = text.split(".").filter(Boolean);
  if (parts.length >= 2) {
    return `...${parts.slice(-2).join(".")}`;
  }
  if (text.length > 18) {
    return `...${text.slice(-14)}`;
  }
  return text;
}

function normalizeString(value: string) {
  return value.trim().toLowerCase();
}

function contextTermKey(term: CompareContextTerm) {
  return [
    normalizeString(term.entity_type),
    normalizeString(term.term),
    normalizeString(term.lang),
    Number(term.weight ?? 0).toString(),
    term.enabled ? "1" : "0",
  ].join("|");
}

function contextTermLabel(term: CompareContextTerm) {
  const entity = term.entity_type || "-";
  const value = term.term || "-";
  const lang = term.lang || "-";
  const weight = Number(term.weight ?? 0);
  const enabled = term.enabled ? "enabled" : "disabled";
  return `${entity}:${value} [${lang}, w=${weight}, ${enabled}]`;
}

function canonicalizeContextTerms(terms: CompareContextTerm[]) {
  return terms.map(contextTermKey).sort();
}

function diffLists(existingValues: string[], draftValues: string[]): ListDiff {
  const existingSet = new Set(existingValues);
  const draftSet = new Set(draftValues);
  const added = draftValues.filter((value) => !existingSet.has(value));
  const removed = existingValues.filter((value) => !draftSet.has(value));
  const unchanged = existingValues.filter((value) => draftSet.has(value));
  return {
    added: dedupeStrings(added),
    removed: dedupeStrings(removed),
    unchanged: dedupeStrings(unchanged),
  };
}

function areStringListsEqual(a: string[], b: string[]) {
  if (a.length !== b.length) {
    return false;
  }
  return a.every((value, index) => value === b[index]);
}

function buildCompareViewModel(
  existingRule: RuleSummary,
  draftRule: RuleSummary,
  existingConditions: ConditionViewModel,
  draftConditions: ConditionViewModel
): CompareViewModel {
  const existingConditionTokens = [...existingConditions.tokens].sort();
  const draftConditionTokens = [...draftConditions.tokens].sort();
  const existingContextKeys = canonicalizeContextTerms(existingRule.contextTerms);
  const draftContextKeys = canonicalizeContextTerms(draftRule.contextTerms);
  const existingContextLabels = existingRule.contextTerms.map(contextTermLabel).sort();
  const draftContextLabels = draftRule.contextTerms.map(contextTermLabel).sort();
  const conditionsDiff = diffLists(existingConditionTokens, draftConditionTokens);
  const contextTermsDiff = diffLists(existingContextLabels, draftContextLabels);
  const conditionsChanged =
    conditionsDiff.added.length > 0 ||
    conditionsDiff.removed.length > 0 ||
    toPrettyJson(existingRule.conditions) !== toPrettyJson(draftRule.conditions);

  const fieldDiff: CompareFieldDiff = {
    action: normalizeString(existingRule.action) !== normalizeString(draftRule.action),
    scope: normalizeString(existingRule.scope) !== normalizeString(draftRule.scope),
    severity: normalizeString(existingRule.severity) !== normalizeString(draftRule.severity),
    priority: Number(existingRule.priority) !== Number(draftRule.priority),
    ragMode: normalizeString(existingRule.ragMode) !== normalizeString(draftRule.ragMode),
    enabled: Boolean(existingRule.enabled) !== Boolean(draftRule.enabled),
    conditions: conditionsChanged,
    contextTerms: !areStringListsEqual(existingContextKeys, draftContextKeys),
  };

  const changedFields = [
    fieldDiff.conditions ? "Conditions" : null,
    fieldDiff.contextTerms ? "Context terms" : null,
    fieldDiff.action ? "Action" : null,
    fieldDiff.priority ? "Priority" : null,
    fieldDiff.severity ? "Severity" : null,
    fieldDiff.enabled ? "Enabled" : null,
    fieldDiff.ragMode ? "RAG mode" : null,
    fieldDiff.scope ? "Scope" : null,
  ].filter((value): value is string => Boolean(value));

  const matchedFields = [
    !fieldDiff.conditions ? "Conditions" : null,
    !fieldDiff.contextTerms ? "Context terms" : null,
    !fieldDiff.action ? "Action" : null,
    !fieldDiff.priority ? "Priority" : null,
    !fieldDiff.severity ? "Severity" : null,
    !fieldDiff.enabled ? "Enabled" : null,
    !fieldDiff.ragMode ? "RAG mode" : null,
    !fieldDiff.scope ? "Scope" : null,
  ].filter((value): value is string => Boolean(value));

  return {
    identical: changedFields.length === 0,
    changedFields,
    matchedFields,
    fieldDiff,
    conditionsDiff,
    contextTermsDiff,
    contextTermsIdentical: !fieldDiff.contextTerms,
  };
}

type DiffStatus = "MATCH" | "CHANGE" | "ADD" | "REMOVE";

function DiffStatusBadge({ status }: { status: DiffStatus }) {
  const tone =
    status === "CHANGE" ? "warning" : status === "REMOVE" ? "danger" : "success";

  return (
    <StatusBadge
      className="text-[10px] font-semibold uppercase tracking-[0.12em]"
      label={status}
      tone={tone}
    />
  );
}

function DiffFieldChip({
  field,
  status,
}: {
  field: string;
  status: "MATCH" | "CHANGE";
}) {
  const cardClassName =
    status === "CHANGE"
      ? "border-warning-border bg-warning-muted"
      : "border-success-border bg-success-muted";

  return (
    <div className={cn("flex items-center gap-2 rounded-xl border px-3 py-2 text-sm", cardClassName)}>
      <DiffStatusBadge status={status} />
      <span className="font-medium text-foreground">{field}</span>
    </div>
  );
}

function DuplicateWarningBanner({
  state,
  similarity,
}: {
  state: DuplicateUiState;
  similarity?: number | null;
}) {
  const matchPercent = toMatchPercent(similarity);

  if (state === "EXACT_DUPLICATE") {
    return (
      <AppAlert
        description="This rule matches an existing rule. Creating a new one would duplicate coverage."
        title={`Exact duplicate detected${typeof matchPercent === "number" ? ` (${matchPercent}% match)` : ""}`}
        variant="error"
      />
    );
  }

  if (state === "NEAR_DUPLICATE") {
    return (
      <AppAlert
        description="A similar rule already exists. Review the differences before continuing."
        title={`Similar rule detected${typeof matchPercent === "number" ? ` (${matchPercent}% match)` : ""}`}
        variant="warning"
      />
    );
  }

  return (
    <AppAlert
      description="This draft looks distinct enough to create as a new rule."
      title="No similar rules found"
      variant="success"
    />
  );
}

function DiffSummaryCard({ compare, state }: { compare: CompareViewModel; state: DuplicateUiState }) {
  return (
    <Card
      className={cn(
        "space-y-4 p-4",
        state === "EXACT_DUPLICATE"
          ? "border-danger-border bg-danger-muted"
          : "border-warning-border bg-warning-muted"
      )}
    >
      <div className="flex items-start gap-2">
        <Info className={cn("mt-0.5 h-4 w-4", state === "EXACT_DUPLICATE" ? "text-danger" : "text-warning")} />
        <div className="space-y-1">
          <p className={cn("text-sm font-semibold", state === "EXACT_DUPLICATE" ? "text-danger" : "text-warning")}>
            {compare.identical ? "Rules match exactly" : "Readable diff summary"}
          </p>
          <p className="text-xs text-muted-foreground">
            {compare.identical
              ? "The draft is identical to the existing rule across all comparable fields."
              : "Review the changed and matched field counts before scanning the detailed side-by-side diff."}
          </p>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-xl border border-warning-border bg-warning-muted px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Changed fields
              </p>
              <p className="mt-1 text-2xl font-semibold text-foreground">
                {compare.changedFields.length}
              </p>
            </div>
            <DiffStatusBadge status="CHANGE" />
          </div>
        </div>
        <div className="rounded-xl border border-success-border bg-success-muted px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Matched fields
              </p>
              <p className="mt-1 text-2xl font-semibold text-foreground">
                {compare.matchedFields.length}
              </p>
            </div>
            <DiffStatusBadge status="MATCH" />
          </div>
        </div>
      </div>

      {compare.changedFields.length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Changed fields
          </p>
          <div className="flex flex-wrap gap-2">
            {compare.changedFields.map((field) => (
              <DiffFieldChip field={field} key={field} status="CHANGE" />
            ))}
          </div>
        </div>
      ) : null}

      {compare.matchedFields.length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Matched fields
          </p>
          <div className="flex flex-wrap gap-2">
            {compare.matchedFields.map((field) => (
              <DiffFieldChip field={field} key={`matched-${field}`} status="MATCH" />
            ))}
          </div>
        </div>
      ) : null}
    </Card>
  );
}

function DiffChip({
  label,
  tone,
}: {
  label: string;
  tone: "added" | "removed" | "match";
}) {
  const status = tone === "added" ? "ADD" : tone === "removed" ? "REMOVE" : "MATCH";
  const className =
    tone === "added"
      ? "border-success-border bg-success-muted"
      : tone === "removed"
        ? "border-danger-border bg-danger-muted"
        : "border-success-border bg-success-muted/60";

  return (
    <li className={cn("flex items-start gap-2 rounded-xl border px-3 py-2 text-xs", className)}>
      <DiffStatusBadge status={status} />
      <span className="pt-0.5 text-foreground">{label}</span>
    </li>
  );
}

function ContextTermsSummary({
  terms,
  wrapperClassName,
}: {
  terms: CompareContextTerm[];
  wrapperClassName?: string;
}) {
  if (!terms.length) {
    return <p className="text-xs text-muted-foreground">No context terms.</p>;
  }

  return (
    <div className={cn("grid gap-2", wrapperClassName)}>
      {terms.map((term, idx) => (
        <div className="rounded-xl border border-border/80 bg-background px-3 py-2" key={`${term.entity_type}-${term.term}-${idx}`}>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-medium text-foreground">{term.term || "-"}</p>
            <StatusBadge label={toTitleCase(term.entity_type || "Unknown")} tone="primary" />
            <StatusBadge status={term.enabled ? "enabled" : "disabled"} />
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Language {term.lang || "-"} | Weight {term.weight}
          </p>
        </div>
      ))}
    </div>
  );
}

function DiffSection({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone: "added" | "removed" | "match";
}) {
  if (items.length === 0) {
    return null;
  }

  const status = tone === "added" ? "ADD" : tone === "removed" ? "REMOVE" : "MATCH";

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <DiffStatusBadge status={status} />
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</p>
      </div>
      <ul className="space-y-2">
        {items.map((value) => (
          <DiffChip key={`${tone}-${value}`} label={value} tone={tone} />
        ))}
      </ul>
    </div>
  );
}

function CompareFieldRow({
  label,
  value,
  changed,
}: {
  label: string;
  value: string;
  changed: boolean;
}) {
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 rounded-xl border px-3 py-2",
        changed
          ? "border-warning-border bg-warning-muted"
          : "border-success-border bg-success-muted"
      )}
    >
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="mt-1 text-sm font-medium text-foreground">{value || "-"}</p>
      </div>
      <DiffStatusBadge status={changed ? "CHANGE" : "MATCH"} />
    </div>
  );
}

function RuleSnapshotCard({
  heading,
  rule,
  conditions,
  showTimestamps = false,
  mode = "view",
  side,
  fieldDiff,
  conditionsDiff,
  contextTermsDiff,
  contextTermsIdentical = false,
}: {
  heading: string;
  rule: RuleSummary;
  conditions: ConditionViewModel;
  showTimestamps?: boolean;
  mode?: RuleInspectorMode;
  side?: "existing" | "draft";
  fieldDiff?: CompareFieldDiff;
  conditionsDiff?: ListDiff;
  contextTermsDiff?: ListDiff;
  contextTermsIdentical?: boolean;
}) {
  const compactId = compactStableKey(rule.stableKey);
  const showConditionDiff = mode === "compare" && fieldDiff?.conditions && conditionsDiff;
  const showExistingRemoved = side === "existing" && (conditionsDiff?.removed.length ?? 0) > 0;
  const showDraftAdded = side === "draft" && (conditionsDiff?.added.length ?? 0) > 0;
  const showContextTermsDiff = mode === "compare" && fieldDiff?.contextTerms && contextTermsDiff;
  const showExistingContextRemoved =
    side === "existing" && (contextTermsDiff?.removed.length ?? 0) > 0;
  const showDraftContextAdded = side === "draft" && (contextTermsDiff?.added.length ?? 0) > 0;
  const showConditionsIdentical = mode === "compare" && !fieldDiff?.conditions;
  const showContextIdentical = mode === "compare" && contextTermsIdentical;
  const conditionStatus: DiffStatus =
    mode === "compare" ? (fieldDiff?.conditions ? "CHANGE" : "MATCH") : "MATCH";
  const contextStatus: DiffStatus =
    mode === "compare" ? (fieldDiff?.contextTerms ? "CHANGE" : "MATCH") : "MATCH";

  return (
    <Card className="space-y-4 p-4">
      <div>
        <h4 className="text-sm font-semibold text-muted-foreground">{heading}</h4>
        <p className="text-base font-semibold text-foreground">{rule.title || "-"}</p>
        {compactId && (
          <p className="text-[11px] text-muted-foreground" title={rule.stableKey}>
            ID: {compactId}
          </p>
        )}
      </div>

      {rule.description && <p className="text-sm text-muted-foreground">{rule.description}</p>}

      <div className="grid gap-2 text-xs md:grid-cols-2">
        <CompareFieldRow
          changed={Boolean(fieldDiff?.action)}
          label="Action"
          value={toTitleCase(rule.action)}
        />
        <CompareFieldRow
          changed={Boolean(fieldDiff?.scope)}
          label="Scope"
          value={toTitleCase(rule.scope)}
        />
        <CompareFieldRow
          changed={Boolean(fieldDiff?.severity)}
          label="Severity"
          value={toTitleCase(rule.severity)}
        />
        <CompareFieldRow
          changed={Boolean(fieldDiff?.priority)}
          label="Priority"
          value={String(rule.priority)}
        />
        <CompareFieldRow
          changed={Boolean(fieldDiff?.ragMode)}
          label="RAG mode"
          value={toTitleCase(rule.ragMode)}
        />
        <CompareFieldRow
          changed={Boolean(fieldDiff?.enabled)}
          label="Enabled"
          value={rule.enabled ? "Yes" : "No"}
        />
      </div>

      {showTimestamps && (
        <div className="grid gap-2 text-xs text-muted-foreground md:grid-cols-2">
          <p>Created: {rule.createdAt || "-"}</p>
          <p>Updated: {rule.updatedAt || "-"}</p>
        </div>
      )}

      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Conditions</p>
          <DiffStatusBadge status={conditionStatus} />
        </div>
        <div
          className={cn(
            "space-y-2 rounded-md border bg-muted/20 p-3",
            fieldDiff?.conditions && "border-warning-border bg-warning-muted/80",
            showConditionsIdentical && "border-sky-200 bg-sky-50/70"
          )}
        >
          {showConditionsIdentical && (
            <p className="rounded-md border border-sky-200 bg-sky-100/60 px-2 py-1 text-xs font-medium text-sky-900">
              MATCH: same readable condition logic as the other side.
            </p>
          )}
          <p className="text-xs font-medium">{conditions.title}</p>
          {conditions.badges.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {conditions.badges.map((badge) => (
                <Badge
                  className={cn(
                    showConditionsIdentical
                      ? "border border-sky-200 bg-sky-100 text-sky-900"
                      : "bg-muted text-muted-foreground"
                  )}
                  key={badge}
                >
                  {badge}
                </Badge>
              ))}
            </div>
          )}
          <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
            {conditions.bullets.map((bullet, index) => (
              <li key={`${bullet}-${index}`}>{bullet}</li>
            ))}
          </ul>

          {showConditionDiff && (
            <div className="space-y-2 rounded-md border bg-background p-2">
              <p className="text-xs font-medium text-warning">Readable condition diff</p>
              <DiffSection items={conditionsDiff.unchanged} title="Matched conditions" tone="match" />
              {showExistingRemoved ? (
                <DiffSection items={conditionsDiff.removed} title="Removed from draft" tone="removed" />
              ) : null}
              {showDraftAdded ? (
                <DiffSection items={conditionsDiff.added} title="Added in draft" tone="added" />
              ) : null}
              {!showExistingRemoved && !showDraftAdded && (
                <p className="text-xs text-muted-foreground">
                  Changes detected, but token-level diff is not available.
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Context terms</p>
          <DiffStatusBadge status={contextStatus} />
        </div>
        <div
          className={cn(
            "space-y-2 rounded-md border bg-muted/10 p-2",
            fieldDiff?.contextTerms && "border-warning-border bg-warning-muted/70",
            showContextIdentical && "border-sky-200 bg-sky-50/70"
          )}
        >
          {showContextIdentical && (
            <p className="rounded-md border border-sky-200 bg-sky-100/60 px-2 py-1 text-xs font-medium text-sky-900">
              MATCH: same context terms as the other side.
            </p>
          )}
          <ContextTermsSummary
            terms={rule.contextTerms}
            wrapperClassName={showContextIdentical ? "rounded-xl border border-sky-200 bg-sky-100/40 p-2" : undefined}
          />
          {showContextTermsDiff && (
            <div className="space-y-2 rounded-md border bg-background p-2">
              <p className="text-xs font-medium text-warning">Readable context diff</p>
              <DiffSection items={contextTermsDiff.unchanged} title="Matched terms" tone="match" />
              {showExistingContextRemoved ? (
                <DiffSection items={contextTermsDiff.removed} title="Removed from draft" tone="removed" />
              ) : null}
              {showDraftContextAdded ? (
                <DiffSection items={contextTermsDiff.added} title="Added in draft" tone="added" />
              ) : null}
              {!showExistingContextRemoved && !showDraftContextAdded && (
                <p className="text-xs text-muted-foreground">
                  Changes detected, but added or removed context terms are not available.
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      <TechnicalDetailsAccordion
        sections={[
          {
            title: "Conditions JSON",
            data: rule.conditions,
          },
          {
            title: "Context terms JSON",
            data: rule.contextTerms,
          },
        ]}
        title="Raw JSON"
      />
    </Card>
  );
}

function CompareActionFooter({
  duplicateState,
  candidateOrigin,
  onEditExistingRule,
  onContinueAnyway,
  onClose,
}: {
  duplicateState: DuplicateUiState;
  candidateOrigin?: string | null;
  onEditExistingRule?: () => void;
  onContinueAnyway?: () => void;
  onClose: () => void;
}) {
  const isGlobalCandidate = isGlobalCandidateOrigin(candidateOrigin);

  if (isGlobalCandidate && duplicateState === "EXACT_DUPLICATE") {
    return (
      <Card className="space-y-3 border-warning-border bg-warning-muted p-3">
        <p className="text-sm text-foreground">
          This match is a global rule. It is managed centrally and should not be recreated as a
          duplicate custom rule.
        </p>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <AppButton onClick={onClose} type="button" variant="secondary">
            Close
          </AppButton>
        </div>
      </Card>
    );
  }

  if (isGlobalCandidate) {
    return (
      <Card className="space-y-3 border-warning-border bg-warning-muted p-3">
        <p className="text-sm text-foreground">
          This candidate is a global rule. You cannot edit it here, but you can adjust whether it
          is enabled from the Rules page.
        </p>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <AppButton onClick={onContinueAnyway ?? onClose} type="button" variant="secondary">
            Continue anyway
          </AppButton>
          <AppButton onClick={onClose} type="button" variant="secondary">
            Cancel
          </AppButton>
        </div>
      </Card>
    );
  }

  if (onEditExistingRule) {
    return (
      <Card className="flex flex-wrap items-center justify-end gap-2 p-3">
        <AppButton onClick={onEditExistingRule} type="button">
          Edit existing rule
        </AppButton>
        <AppButton onClick={onContinueAnyway ?? onClose} type="button" variant="secondary">
          Continue anyway
        </AppButton>
        <AppButton onClick={onClose} type="button" variant="secondary">
          Cancel
        </AppButton>
      </Card>
    );
  }

  if (duplicateState === "NO_DUPLICATE") {
    return (
      <Card className="flex flex-wrap items-center justify-end gap-2 p-3">
        <AppButton onClick={onContinueAnyway ?? onClose} type="button">
          Create new rule
        </AppButton>
        <AppButton onClick={onClose} type="button" variant="secondary">
          Cancel
        </AppButton>
      </Card>
    );
  }

  if (duplicateState === "EXACT_DUPLICATE") {
    return (
      <Card className="flex flex-wrap items-center justify-end gap-2 p-3">
        <AppButton onClick={onEditExistingRule} type="button">
          Edit existing rule
        </AppButton>
        <AppButton onClick={onClose} type="button" variant="secondary">
          Cancel
        </AppButton>
        <AppButton onClick={onContinueAnyway ?? onClose} type="button" variant="secondary">
          Continue anyway
        </AppButton>
      </Card>
    );
  }

  return (
    <Card className="flex flex-wrap items-center justify-end gap-2 p-3">
      <AppButton onClick={onEditExistingRule} type="button">
        Edit existing rule
      </AppButton>
      <AppButton onClick={onContinueAnyway ?? onClose} type="button" variant="secondary">
        Continue anyway
      </AppButton>
      <AppButton onClick={onClose} type="button" variant="secondary">
        Cancel
      </AppButton>
    </Card>
  );
}

export function SuggestionRuleInspectorDialog({
  open,
  mode,
  candidateName,
  candidateOrigin,
  existingRule,
  draft,
  isLoading,
  errorMessage,
  duplicateDecision,
  candidateSimilarity,
  onRetry,
  onEditExistingRule,
  onContinueAnyway,
  onClose,
}: SuggestionRuleInspectorDialogProps) {
  if (!open) {
    return null;
  }

  const draftSummary = normalizeDraftRule(draft);
  const existingSummary = existingRule ? normalizeExistingRule(existingRule) : null;
  const title = mode === "compare" ? "Compare Rules" : "Rule Detail";
  const subtitle =
    mode === "compare"
      ? "Compare existing rule with current draft suggestion."
      : "View existing rule without leaving Suggestion detail.";

  const existingConditions = existingSummary
    ? buildConditionViewModel(existingSummary.conditions)
    : null;
  const draftConditions = buildConditionViewModel(draftSummary.conditions);
  const compare =
    mode === "compare" && existingSummary && existingConditions
      ? buildCompareViewModel(existingSummary, draftSummary, existingConditions, draftConditions)
      : null;
  const duplicateState: DuplicateUiState =
    mode !== "compare"
      ? "NO_DUPLICATE"
      : compare?.identical
        ? "EXACT_DUPLICATE"
        : resolveDuplicateUiState({
            decision: duplicateDecision,
            candidatesCount: typeof candidateSimilarity === "number" ? 1 : 0,
            topSimilarity: candidateSimilarity,
          });
  const description = candidateName
    ? `${subtitle} Candidate: ${candidateName}.`
    : subtitle;
  const footer =
    mode === "compare" && existingSummary && existingConditions ? (
      <CompareActionFooter
        candidateOrigin={candidateOrigin}
        duplicateState={duplicateState}
        onClose={onClose}
        onContinueAnyway={onContinueAnyway}
        onEditExistingRule={onEditExistingRule}
      />
    ) : undefined;

  return (
    <AppModal
      bodyClassName="flex h-full min-h-0 flex-col"
      description={description}
      footer={footer}
      onClose={onClose}
      open={open}
      size="xl"
      title={title}
    >
      <ScrollArea className="h-full min-h-0 pr-2">
          {mode === "compare" && (
            <div className="mb-3 space-y-2">
              <DuplicateWarningBanner similarity={candidateSimilarity} state={duplicateState} />
              {compare && <DiffSummaryCard compare={compare} state={duplicateState} />}
            </div>
          )}

          {isLoading && (
            <AppLoadingState
              compact
              description="Loading the existing rule before showing the comparison."
              title="Loading rule detail"
            />
          )}

          {!isLoading && errorMessage && (
            <AppAlert title="Unable to load rule detail" variant="error">
              <p className="text-sm text-muted-foreground">{errorMessage}</p>
              {onRetry ? (
                <div className="pt-2">
                  <AppButton onClick={onRetry} size="sm" type="button" variant="secondary">
                    Retry
                  </AppButton>
                </div>
              ) : null}
            </AppAlert>
          )}

          {!isLoading && !errorMessage && !existingSummary && (
            <EmptyState
              description="The selected rule detail could not be loaded for this comparison."
              title="Rule detail unavailable"
            />
          )}

          {!isLoading && !errorMessage && existingSummary && existingConditions && mode === "view" && (
            <RuleSnapshotCard
              conditions={existingConditions}
              heading="Existing rule"
              rule={existingSummary}
              showTimestamps
            />
          )}

          {!isLoading && !errorMessage && existingSummary && existingConditions && mode === "compare" && (
            <div className="space-y-3">
              <div className="grid gap-3 lg:grid-cols-2">
                <RuleSnapshotCard
                  conditions={existingConditions}
                  conditionsDiff={compare?.conditionsDiff}
                  contextTermsDiff={compare?.contextTermsDiff}
                  contextTermsIdentical={Boolean(compare?.contextTermsIdentical)}
                  fieldDiff={compare?.fieldDiff}
                  heading="Existing rule"
                  mode="compare"
                  rule={existingSummary}
                  side="existing"
                />
                <RuleSnapshotCard
                  conditions={draftConditions}
                  conditionsDiff={compare?.conditionsDiff}
                  contextTermsDiff={compare?.contextTermsDiff}
                  contextTermsIdentical={Boolean(compare?.contextTermsIdentical)}
                  fieldDiff={compare?.fieldDiff}
                  heading="Draft suggestion"
                  mode="compare"
                  rule={draftSummary}
                  side="draft"
                />
              </div>
            </div>
          )}
      </ScrollArea>
    </AppModal>
  );
}

