import { AlertTriangle, CheckCircle2, Info } from "lucide-react";
import type { RuleDetail } from "@/features/rules/types";
import type { SuggestionDraft } from "@/features/suggestions/types";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { cn } from "@/shared/lib/utils";
import { ScrollArea } from "@/shared/ui/scroll-area";

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
  fieldDiff: CompareFieldDiff;
  conditionsDiff: ListDiff;
  contextTermsIdentical: boolean;
};

type SuggestionRuleInspectorDialogProps = {
  open: boolean;
  mode: RuleInspectorMode;
  candidateName?: string;
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
  const conditionsDiff = diffLists(existingConditionTokens, draftConditionTokens);
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
    fieldDiff.action ? "Action" : null,
    fieldDiff.priority ? "Priority" : null,
    fieldDiff.severity ? "Severity" : null,
    fieldDiff.enabled ? "Enabled" : null,
    fieldDiff.scope ? "Scope" : null,
    fieldDiff.ragMode ? "Rag mode" : null,
    fieldDiff.contextTerms ? "Context terms" : null,
  ].filter((value): value is string => Boolean(value));

  return {
    identical: changedFields.length === 0,
    changedFields,
    fieldDiff,
    conditionsDiff,
    contextTermsIdentical: !fieldDiff.contextTerms,
  };
}

function DuplicateWarningBanner({
  decision,
  similarity,
}: {
  decision?: string | null;
  similarity?: number | null;
}) {
  const normalized = String(decision || "").trim().toUpperCase();
  const matchPercent = toMatchPercent(similarity);

  if (normalized === "EXACT_DUPLICATE") {
    return (
      <Card className="border-red-300 bg-red-50 p-3">
        <div className="flex items-start gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 text-red-700" />
          <div className="space-y-1">
            <p className="text-sm font-semibold text-red-800">
              Exact duplicate detected
              {typeof matchPercent === "number" ? ` (${matchPercent}% match)` : ""}
            </p>
            <p className="text-xs text-red-700">
              This rule is effectively identical to an existing rule. Creating a new rule may
              cause redundancy.
            </p>
          </div>
        </div>
      </Card>
    );
  }

  if (normalized === "NEAR_DUPLICATE") {
    return (
      <Card className="border-amber-300 bg-amber-50 p-3">
        <div className="flex items-start gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-700" />
          <div className="space-y-1">
            <p className="text-sm font-semibold text-amber-800">
              Similar rule detected
              {typeof matchPercent === "number"
                ? ` (${matchPercent}% match)`
                : " (~85-95% match)"}
            </p>
            <p className="text-xs text-amber-700">
              Review differences before continuing to avoid overlapping behavior.
            </p>
          </div>
        </div>
      </Card>
    );
  }

  return null;
}

function DiffSummaryCard({ compare }: { compare: CompareViewModel }) {
  if (compare.identical) {
    return (
      <Card className="border-emerald-300 bg-emerald-50 p-3">
        <div className="flex items-start gap-2">
          <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-700" />
          <div className="space-y-1">
            <p className="text-sm font-semibold text-emerald-800">
              No differences found. This rule is identical.
            </p>
            <p className="text-xs text-emerald-700">
              Recommended action: edit the existing rule instead of creating a duplicate.
            </p>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="border-amber-300 bg-amber-50 p-3">
      <div className="flex items-start gap-2">
        <Info className="mt-0.5 h-4 w-4 text-amber-700" />
        <div className="space-y-2">
          <p className="text-sm font-semibold text-amber-800">Differences found</p>
          <p className="text-xs text-amber-700">Changed fields:</p>
          <div className="flex flex-wrap gap-1">
            {compare.changedFields.map((field) => (
              <Badge className="bg-amber-100 text-amber-800" key={field}>
                {field}
              </Badge>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
}

function DiffChip({
  label,
  tone,
  prefix,
}: {
  label: string;
  tone: "added" | "removed";
  prefix: "+" | "-";
}) {
  return (
    <li
      className={cn(
        "rounded border px-2 py-1 text-xs",
        tone === "added"
          ? "border-emerald-300 bg-emerald-50 text-emerald-800"
          : "border-rose-300 bg-rose-50 text-rose-800"
      )}
    >
      {prefix} {label}
    </li>
  );
}

function ContextTermsTable({ terms }: { terms: CompareContextTerm[] }) {
  if (!terms.length) {
    return <p className="text-xs text-muted-foreground">No context terms.</p>;
  }

  return (
    <div className="overflow-auto rounded-md border">
      <table className="w-full text-left text-xs">
        <thead className="bg-muted/40">
          <tr>
            <th className="px-2 py-1 font-medium">Entity</th>
            <th className="px-2 py-1 font-medium">Term</th>
            <th className="px-2 py-1 font-medium">Lang</th>
            <th className="px-2 py-1 font-medium">Weight</th>
            <th className="px-2 py-1 font-medium">Enabled</th>
          </tr>
        </thead>
        <tbody>
          {terms.map((term, idx) => (
            <tr className="border-t" key={`${term.entity_type}-${term.term}-${idx}`}>
              <td className="px-2 py-1">{term.entity_type || "-"}</td>
              <td className="px-2 py-1">{term.term || "-"}</td>
              <td className="px-2 py-1">{term.lang || "-"}</td>
              <td className="px-2 py-1">{term.weight}</td>
              <td className="px-2 py-1">{term.enabled ? "Yes" : "No"}</td>
            </tr>
          ))}
        </tbody>
      </table>
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
    <p
      className={cn(
        "rounded px-2 py-1",
        changed ? "border border-amber-300 bg-amber-50 text-amber-900" : "border border-transparent"
      )}
    >
      {label}: {value || "-"}
    </p>
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
  contextTermsIdentical?: boolean;
}) {
  const compactId = compactStableKey(rule.stableKey);
  const showConditionDiff = mode === "compare" && fieldDiff?.conditions && conditionsDiff;
  const showExistingRemoved = side === "existing" && (conditionsDiff?.removed.length ?? 0) > 0;
  const showDraftAdded = side === "draft" && (conditionsDiff?.added.length ?? 0) > 0;
  const showCollapsedTerms = mode === "compare" && contextTermsIdentical;

  return (
    <Card className="space-y-3 p-3">
      <div>
        <h4 className="text-sm font-semibold">{heading}</h4>
        <p className="text-sm">{rule.title || "-"}</p>
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
          label="Rag mode"
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
        <p className="text-xs font-medium text-muted-foreground">Conditions</p>
        <div
          className={cn(
            "space-y-2 rounded-md border bg-muted/20 p-3",
            fieldDiff?.conditions && "border-amber-300 bg-amber-50/60"
          )}
        >
          <p className="text-xs font-medium">{conditions.title}</p>
          {conditions.badges.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {conditions.badges.map((badge) => (
                <Badge className="bg-muted text-muted-foreground" key={badge}>
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
              <p className="text-xs font-medium text-amber-800">Condition changes</p>
              {showExistingRemoved && (
                <ul className="space-y-1">
                  {conditionsDiff.removed.map((value) => (
                    <DiffChip key={`removed-${value}`} label={value} prefix="-" tone="removed" />
                  ))}
                </ul>
              )}
              {showDraftAdded && (
                <ul className="space-y-1">
                  {conditionsDiff.added.map((value) => (
                    <DiffChip key={`added-${value}`} label={value} prefix="+" tone="added" />
                  ))}
                </ul>
              )}
              {!showExistingRemoved && !showDraftAdded && (
                <p className="text-xs text-muted-foreground">
                  Conditions changed, but token-level diff is not available.
                </p>
              )}
            </div>
          )}
        </div>
        <details className="rounded-md border bg-muted/30 p-2">
          <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
            View raw JSON
          </summary>
          <pre className="mt-2 max-h-64 overflow-auto rounded-md border bg-background p-2 text-[11px]">
            {toPrettyJson(rule.conditions)}
          </pre>
        </details>
      </div>

      <div className="space-y-1">
        <p className="text-xs font-medium text-muted-foreground">Context terms</p>
        <div
          className={cn(
            "space-y-2 rounded-md border bg-muted/10 p-2",
            fieldDiff?.contextTerms && "border-amber-300 bg-amber-50/40"
          )}
        >
          {showCollapsedTerms ? (
            <>
              <p className="text-xs text-muted-foreground">Context terms: identical</p>
              <details>
                <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
                  View context terms
                </summary>
                <div className="mt-2">
                  <ContextTermsTable terms={rule.contextTerms} />
                </div>
              </details>
            </>
          ) : (
            <ContextTermsTable terms={rule.contextTerms} />
          )}
        </div>
      </div>
    </Card>
  );
}

export function SuggestionRuleInspectorDialog({
  open,
  mode,
  candidateName,
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="flex w-full max-w-6xl flex-col gap-3 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold">{title}</h3>
            <p className="text-sm text-muted-foreground">{subtitle}</p>
            {candidateName && (
              <p className="text-xs text-muted-foreground">Candidate: {candidateName}</p>
            )}
          </div>
          <Button onClick={onClose} size="sm" type="button" variant="outline">
            Close
          </Button>
        </div>

        <ScrollArea className="max-h-[80vh]">
          {mode === "compare" && (
            <div className="mb-3 space-y-2">
              <DuplicateWarningBanner decision={duplicateDecision} similarity={candidateSimilarity} />
              {compare && <DiffSummaryCard compare={compare} />}
            </div>
          )}

          {isLoading && (
            <Card className="border-dashed p-4 text-sm text-muted-foreground">
              Loading rule detail...
            </Card>
          )}

          {!isLoading && errorMessage && (
            <Card className="space-y-3 border-destructive/30 bg-destructive/10 p-4">
              <p className="text-sm text-destructive">{errorMessage}</p>
              {onRetry && (
                <Button onClick={onRetry} size="sm" type="button" variant="outline">
                  Retry
                </Button>
              )}
            </Card>
          )}

          {!isLoading && !errorMessage && !existingSummary && (
            <Card className="p-4 text-sm text-muted-foreground">
              Rule detail is unavailable.
            </Card>
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
                  contextTermsIdentical={Boolean(compare?.contextTermsIdentical)}
                  fieldDiff={compare?.fieldDiff}
                  heading="Draft suggestion"
                  mode="compare"
                  rule={draftSummary}
                  side="draft"
                />
              </div>

              <Card className="flex flex-wrap items-center justify-end gap-2 p-3">
                <Button onClick={onEditExistingRule} type="button">
                  Edit existing rule
                </Button>
                <Button onClick={onContinueAnyway ?? onClose} type="button" variant="outline">
                  Continue anyway
                </Button>
                <Button onClick={onClose} type="button" variant="ghost">
                  Cancel
                </Button>
              </Card>
            </div>
          )}
        </ScrollArea>
      </Card>
    </div>
  );
}
