import { type ReactNode, useEffect, useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import type { SuggestionDraft } from "@/features/suggestions/types";
import { SuggestionContextTermsEditor } from "@/features/suggestions/components/SuggestionContextTermsEditor";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Textarea } from "@/shared/ui/textarea";

type DraftEditorProps = {
  draft: SuggestionDraft;
  readOnly?: boolean;
  validationError?: string | null;
  onDraftChange: (nextDraft: SuggestionDraft) => void;
};

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
  const minScore = typeof item.min_score === "number" ? item.min_score : toNumber(String(item.min_score ?? "0"), 0);

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
    return "No conditions";
  }

  const simple = getSimpleCondition(conditions);
  if (simple) {
    return `Entity match: ${simple.entity_type} (min_score >= ${simple.min_score})`;
  }

  if (Array.isArray(conditions.any)) {
    return `any: ${conditions.any.length} condition nodes`;
  }
  if (Array.isArray(conditions.all)) {
    return `all: ${conditions.all.length} condition nodes`;
  }
  if (conditions.not) {
    return "not: 1 condition node";
  }

  return "Complex conditions format. Check Advanced JSON.";
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
      setAdvancedError("Invalid JSON format in Advanced section.");
    }
  };

  return (
    <div className="space-y-4">
      {validationError && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 h-4 w-4" />
          <span>{validationError}</span>
        </div>
      )}

      <div className="grid gap-4 rounded-md border p-4 md:grid-cols-2">
        <Field label="Stable key">
          <Input
            disabled={readOnly}
            onChange={(event) => updateRuleField("stable_key", event.target.value)}
            value={draft.rule.stable_key ?? ""}
          />
        </Field>

        <Field label="Name">
          <Input
            disabled={readOnly}
            onChange={(event) => updateRuleField("name", event.target.value)}
            value={draft.rule.name ?? ""}
          />
        </Field>

        <div className="space-y-1.5 md:col-span-2">
          <Label>Description</Label>
          <Textarea
            disabled={readOnly}
            onChange={(event) => updateRuleField("description", event.target.value)}
            rows={2}
            value={draft.rule.description ?? ""}
          />
        </div>

        <Field label="Scope">
          <Input
            disabled={readOnly}
            onChange={(event) => updateRuleField("scope", event.target.value)}
            value={draft.rule.scope ?? ""}
          />
        </Field>

        <Field label="Action">
          <Input
            disabled={readOnly}
            onChange={(event) => updateRuleField("action", event.target.value)}
            value={draft.rule.action ?? ""}
          />
        </Field>

        <Field label="Severity">
          <Input
            disabled={readOnly}
            onChange={(event) => updateRuleField("severity", event.target.value)}
            value={draft.rule.severity ?? ""}
          />
        </Field>

        <Field label="Priority">
          <Input
            disabled={readOnly}
            onChange={(event) => updateRuleField("priority", toNumber(event.target.value, 0))}
            type="number"
            value={draft.rule.priority ?? 0}
          />
        </Field>

        <Field label="RAG mode">
          <Input
            disabled={readOnly}
            onChange={(event) => updateRuleField("rag_mode", event.target.value)}
            value={draft.rule.rag_mode ?? ""}
          />
        </Field>

        <Field label="Status">
          <div>
            <label
              className="inline-flex w-fit items-center gap-2 rounded-md border px-3 py-2 text-sm"
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
              <span className="leading-none">Enabled</span>
            </label>
          </div>
        </Field>
      </div>

      <div className="space-y-2 rounded-md border p-4">
        <h4 className="text-sm font-semibold">Conditions</h4>
        <p className="text-sm text-muted-foreground">{conditionsSummary}</p>

        {simpleCondition && (
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Entity type">
              <Input
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
              />
            </Field>

            <Field label="Min score">
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
        )}
      </div>

      <div className="rounded-md border p-4">
        <SuggestionContextTermsEditor
          onChange={(nextTerms) => onDraftChange({ ...draft, context_terms: nextTerms })}
          readOnly={readOnly}
          terms={draft.context_terms}
        />
      </div>

      <details className="rounded-md border p-3 text-sm">
        <summary className="cursor-pointer font-medium">Advanced JSON</summary>
        <p className="mt-2 text-xs text-muted-foreground">
          For developer/debug only. You can edit raw JSON and apply it back to the form.
        </p>

        <div className="mt-3 space-y-3">
          <div className="space-y-1.5">
            <Label>Raw draft.rule JSON</Label>
            <Textarea
              className="min-h-[180px] font-mono text-xs"
              disabled={readOnly}
              onChange={(event) => setRawRuleJson(event.target.value)}
              value={rawRuleJson}
            />
          </div>

          <div className="space-y-1.5">
            <Label>Raw context_terms JSON</Label>
            <Textarea
              className="min-h-[160px] font-mono text-xs"
              disabled={readOnly}
              onChange={(event) => setRawTermsJson(event.target.value)}
              value={rawTermsJson}
            />
          </div>

          {advancedError && <p className="text-xs text-destructive">{advancedError}</p>}

          <div className="flex justify-end">
            <Button
              disabled={readOnly}
              onClick={applyAdvancedJson}
              size="sm"
              type="button"
              variant="outline"
            >
              Apply JSON to form
            </Button>
          </div>
        </div>
      </details>

      {readOnly && (
        <p className="text-xs text-muted-foreground">
          Draft is read-only because suggestion is no longer in draft status.
        </p>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

