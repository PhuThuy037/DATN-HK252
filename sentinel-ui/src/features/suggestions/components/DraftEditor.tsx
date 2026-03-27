import { type ReactNode, useEffect, useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import type { SuggestionDraft } from "@/features/suggestions/types";
import { SuggestionContextTermsEditor } from "@/features/suggestions/components/SuggestionContextTermsEditor";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppButton } from "@/shared/ui/app-button";
import { FieldHelpText } from "@/shared/ui/field-help-text";
import { Input } from "@/shared/ui/input";
import { InlineErrorText } from "@/shared/ui/inline-error-text";
import { Label } from "@/shared/ui/label";
import { StatusBadge } from "@/shared/ui/status-badge";
import { appSelectControlClassName } from "@/shared/ui/design-tokens";
import { Textarea } from "@/shared/ui/textarea";

type DraftEditorProps = {
  draft: SuggestionDraft;
  readOnly?: boolean;
  validationError?: string | null;
  onDraftChange: (nextDraft: SuggestionDraft) => void;
};

const sectionCardClassName = "space-y-4 rounded-xl border border-border/80 bg-background p-4 md:p-5";
const scopeOptions = ["prompt", "chat", "file", "api"] as const;
const actionOptions = ["allow", "mask", "block", "warn"] as const;
const severityOptions = ["low", "medium", "high"] as const;
const ragModeOptions = ["off", "explain", "verify"] as const;
const entityTypeOptions = [
  "CUSTOM_SECRET",
  "INTERNAL_CODE",
  "PROPRIETARY_IDENTIFIER",
  "API_SECRET",
  "PHONE",
  "EMAIL",
  "CCCD",
  "PERSON",
  "ADDRESS",
  "ORG",
  "TAX_ID",
  "CREDIT_CARD",
  "OTHER",
] as const;

function toNumber(value: string, fallback = 0) {
  const parsed = Number(value);
  return Number.isNaN(parsed) ? fallback : parsed;
}

function getSimpleCondition(conditions: Record<string, unknown> | undefined) {
  if (!conditions) {
    return null;
  }

  const anyNode = conditions.any;
  if (!Array.isArray(anyNode) || anyNode.length !== 1) {
    return null;
  }

  const first = anyNode[0];
  if (!first || typeof first !== "object" || Array.isArray(first)) {
    return null;
  }

  const item = first as Record<string, unknown>;
  const entityType = String(item.entity_type ?? "").trim();
  const minScore =
    typeof item.min_score === "number"
      ? item.min_score
      : toNumber(String(item.min_score ?? "0"), 0);

  if (!entityType) {
    return null;
  }

  return {
    entity_type: entityType,
    min_score: minScore,
  };
}

function summarizeConditions(conditions: Record<string, unknown> | undefined) {
  if (!conditions || Object.keys(conditions).length === 0) {
    return "No conditions configured yet.";
  }

  const simple = getSimpleCondition(conditions);
  if (simple) {
    return `Entity match: ${simple.entity_type} with a minimum score of ${simple.min_score}.`;
  }

  if (Array.isArray(conditions.any)) {
    return `Matches any of ${conditions.any.length} condition node${conditions.any.length === 1 ? "" : "s"}.`;
  }
  if (Array.isArray(conditions.all)) {
    return `Matches all of ${conditions.all.length} condition node${conditions.all.length === 1 ? "" : "s"}.`;
  }
  if (conditions.not) {
    return "Uses an inverted condition node.";
  }

  return "Complex condition structure detected. Review it in Advanced settings.";
}

function renderSelectOptions(options: readonly string[]) {
  return options.map((option) => (
    <option key={option} value={option}>
      {option}
    </option>
  ));
}

export function DraftEditor({
  draft,
  readOnly = false,
  validationError,
  onDraftChange,
}: DraftEditorProps) {
  const [rawRuleJson, setRawRuleJson] = useState(JSON.stringify(draft.rule, null, 2));
  const [rawTermsJson, setRawTermsJson] = useState(JSON.stringify(draft.context_terms, null, 2));
  const [advancedError, setAdvancedError] = useState<string | null>(null);

  useEffect(() => {
    setRawRuleJson(JSON.stringify(draft.rule, null, 2));
    setRawTermsJson(JSON.stringify(draft.context_terms, null, 2));
    setAdvancedError(null);
  }, [draft]);

  const simpleCondition = useMemo(() => getSimpleCondition(draft.rule.conditions), [draft.rule.conditions]);
  const conditionsSummary = useMemo(
    () => summarizeConditions(draft.rule.conditions),
    [draft.rule.conditions]
  );

  const updateRuleField = <K extends keyof SuggestionDraft["rule"]>(
    field: K,
    value: SuggestionDraft["rule"][K]
  ) => {
    onDraftChange({
      ...draft,
      rule: {
        ...draft.rule,
        [field]: value,
      },
    });
  };

  const applyAdvancedJson = () => {
    try {
      const nextRule = JSON.parse(rawRuleJson) as SuggestionDraft["rule"];
      const nextTerms = JSON.parse(rawTermsJson) as SuggestionDraft["context_terms"];

      if (!nextRule || typeof nextRule !== "object" || Array.isArray(nextRule)) {
        setAdvancedError("Rule JSON must be an object.");
        return;
      }
      if (!Array.isArray(nextTerms)) {
        setAdvancedError("Context terms JSON must be an array.");
        return;
      }

      setAdvancedError(null);
      onDraftChange({
        rule: nextRule,
        context_terms: nextTerms,
      });
    } catch {
      setAdvancedError("Invalid JSON format in Advanced settings.");
    }
  };

  return (
    <div className="space-y-4">
      {validationError ? (
        <AppAlert
          description={validationError}
          icon={<AlertTriangle className="mt-0.5 h-4 w-4 text-danger" />}
          title="Draft validation issue"
          variant="error"
        />
      ) : null}

      <section className={sectionCardClassName}>
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-foreground">Basic info</h3>
          <p className="text-sm text-muted-foreground">
            Define the rule identity and business-facing description first.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Field
            helper="Clear, human-readable title used throughout review and comparison screens."
            label="Rule name"
          >
            <Input
              disabled={readOnly}
              onChange={(event) => updateRuleField("name", event.target.value)}
              value={draft.rule.name ?? ""}
            />
          </Field>

          <Field
            className="md:col-span-2"
            helper="Explain what the rule is intended to protect, detect, or enforce."
            label="Description"
          >
            <Textarea
              disabled={readOnly}
              onChange={(event) => updateRuleField("description", event.target.value)}
              rows={3}
              value={draft.rule.description ?? ""}
            />
          </Field>
        </div>
      </section>

      <section className={sectionCardClassName}>
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-foreground">Behavior</h3>
          <p className="text-sm text-muted-foreground">
            Control how the rule behaves once it matches content.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <Field helper="Primary outcome when the rule matches." label="Action">
            <select
              className={appSelectControlClassName}
              disabled={readOnly}
              onChange={(event) => updateRuleField("action", event.target.value)}
              value={draft.rule.action ?? ""}
            >
              {renderSelectOptions(actionOptions)}
            </select>
          </Field>

          <Field helper="Where the rule should apply." label="Scope">
            <select
              className={appSelectControlClassName}
              disabled={readOnly}
              onChange={(event) => updateRuleField("scope", event.target.value)}
              value={draft.rule.scope ?? ""}
            >
              {renderSelectOptions(scopeOptions)}
            </select>
          </Field>

          <Field helper="Impact level used for review and prioritization." label="Severity">
            <select
              className={appSelectControlClassName}
              disabled={readOnly}
              onChange={(event) => updateRuleField("severity", event.target.value)}
              value={draft.rule.severity ?? ""}
            >
              {renderSelectOptions(severityOptions)}
            </select>
          </Field>

          <Field helper="How retrieval or explanation should interact with this rule." label="RAG mode">
            <select
              className={appSelectControlClassName}
              disabled={readOnly}
              onChange={(event) => updateRuleField("rag_mode", event.target.value)}
              value={draft.rule.rag_mode ?? ""}
            >
              {renderSelectOptions(ragModeOptions)}
            </select>
          </Field>

          <Field helper="Disabled rules stay in the draft but do not apply when activated." label="Status">
            <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border/80 bg-background px-3 py-2">
              <StatusBadge status={draft.rule.enabled ? "enabled" : "disabled"} />
              <label
                className="inline-flex w-fit items-center gap-2 text-sm text-foreground"
                htmlFor="draft-enabled"
              >
                <input
                  className="h-4 w-4 shrink-0 align-middle"
                  checked={draft.rule.enabled}
                  disabled={readOnly}
                  id="draft-enabled"
                  onChange={(event) => updateRuleField("enabled", event.target.checked)}
                  type="checkbox"
                />
                <span className="leading-none">
                  {draft.rule.enabled ? "Enabled" : "Disabled"}
                </span>
              </label>
            </div>
          </Field>
        </div>
      </section>

      <section className={sectionCardClassName}>
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-foreground">Conditions</h3>
          <p className="text-sm text-muted-foreground">
            Define what content should trigger this rule.
          </p>
        </div>

        <div className="rounded-xl border border-border/80 bg-muted/20 px-4 py-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Current summary
          </p>
          <p className="mt-1 text-sm text-foreground">{conditionsSummary}</p>
        </div>

        {simpleCondition ? (
          <div className="grid gap-4 md:grid-cols-2">
            <Field
              helper="Primary entity family that this simplified condition should match."
              label="Entity type"
            >
              <select
                className={appSelectControlClassName}
                disabled={readOnly}
                onChange={(event) => {
                  updateRuleField("conditions", {
                    any: [
                      {
                        entity_type: event.target.value,
                        min_score: simpleCondition.min_score,
                      },
                    ],
                  });
                }}
                value={simpleCondition.entity_type}
              >
                {renderSelectOptions(entityTypeOptions)}
              </select>
            </Field>

            <Field
              helper="Minimum detection score required before this entity match should trigger."
              label="Minimum score"
            >
              <Input
                disabled={readOnly}
                max={1}
                min={0}
                onChange={(event) => {
                  updateRuleField("conditions", {
                    any: [
                      {
                        entity_type: simpleCondition.entity_type,
                        min_score: toNumber(event.target.value, simpleCondition.min_score),
                      },
                    ],
                  });
                }}
                step="0.01"
                type="number"
                value={simpleCondition.min_score}
              />
            </Field>
          </div>
        ) : (
          <AppAlert
            description="This draft uses a more complex condition structure. Keep using the readable summary here, then review or edit the raw JSON under Advanced settings if needed."
            title="Complex conditions detected"
            variant="info"
          />
        )}
      </section>

      <section className={sectionCardClassName}>
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-foreground">Context terms</h3>
          <p className="text-sm text-muted-foreground">
            Add supporting keywords and entities that help the rule match the right content.
          </p>
        </div>

        <SuggestionContextTermsEditor
          onChange={(nextTerms) => onDraftChange({ ...draft, context_terms: nextTerms })}
          readOnly={readOnly}
          terms={draft.context_terms}
        />
      </section>

      <details className="rounded-xl border border-border/80 bg-muted/10 p-4 text-sm">
        <summary className="cursor-pointer font-medium text-foreground">Advanced settings</summary>
        <p className="mt-2 text-xs text-muted-foreground">
          Internal tuning and developer-facing JSON controls. Most reviews do not need these.
        </p>

        <div className="mt-4 space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Field
              helper="Internal identity key. Change carefully if this draft is meant to update an existing rule."
              label="Stable key"
            >
              <Input
                disabled={readOnly}
                onChange={(event) => updateRuleField("stable_key", event.target.value)}
                value={draft.rule.stable_key ?? ""}
              />
            </Field>

            <Field
              helper="Higher numbers generally win when multiple rules match."
              label="Priority"
            >
              <Input
                disabled={readOnly}
                onChange={(event) => updateRuleField("priority", toNumber(event.target.value, 0))}
                type="number"
                value={draft.rule.priority ?? 0}
              />
            </Field>
          </div>

          <div className="space-y-3 rounded-xl border border-border/80 bg-background p-4">
            <div className="space-y-1">
              <h4 className="text-sm font-semibold text-foreground">Raw JSON</h4>
              <p className="text-xs text-muted-foreground">
                Use only for debugging or complex edits that are not represented by the simplified form.
              </p>
            </div>

            <Field label="Raw `draft.rule` JSON">
              <Textarea
                className="min-h-[180px] font-mono text-xs"
                disabled={readOnly}
                onChange={(event) => setRawRuleJson(event.target.value)}
                value={rawRuleJson}
              />
            </Field>

            <Field label="Raw `context_terms` JSON">
              <Textarea
                className="min-h-[160px] font-mono text-xs"
                disabled={readOnly}
                onChange={(event) => setRawTermsJson(event.target.value)}
                value={rawTermsJson}
              />
            </Field>

            {advancedError ? <InlineErrorText>{advancedError}</InlineErrorText> : null}

            <div className="flex justify-end">
              <AppButton
                disabled={readOnly}
                onClick={applyAdvancedJson}
                size="sm"
                type="button"
                variant="secondary"
              >
                Apply JSON to form
              </AppButton>
            </div>
          </div>
        </div>
      </details>

      {readOnly ? (
        <FieldHelpText>
          Draft is read-only because the suggestion is no longer in draft status.
        </FieldHelpText>
      ) : null}
    </div>
  );
}

function Field({
  label,
  helper,
  className,
  children,
}: {
  label: string;
  helper?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={`space-y-1.5 ${className ?? ""}`}>
      <Label>{label}</Label>
      {children}
      {helper ? <FieldHelpText>{helper}</FieldHelpText> : null}
    </div>
  );
}
