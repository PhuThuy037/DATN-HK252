import { useEffect, useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import type { SuggestionDraft } from "@/features/suggestions/types";
import { SuggestionContextTermsEditor } from "@/features/suggestions/components/SuggestionContextTermsEditor";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppButton } from "@/shared/ui/app-button";
import { appSelectControlClassName } from "@/shared/ui/design-tokens";
import { FieldHelpText } from "@/shared/ui/field-help-text";
import { Input } from "@/shared/ui/input";
import { InlineErrorText } from "@/shared/ui/inline-error-text";
import { Label } from "@/shared/ui/label";
import { StatusBadge } from "@/shared/ui/status-badge";
import { Textarea } from "@/shared/ui/textarea";

type DraftEditorProps = {
  draft: SuggestionDraft;
  readOnly?: boolean;
  validationError?: string | null;
  onDraftChange: (nextDraft: SuggestionDraft) => void;
};

type BuilderLogic = "any" | "all";
type BuilderRow = {
  id: string;
  type: "entity_match" | "signal_keyword_match";
  entityType: string;
  minScore: string;
  keywordsText: string;
};

const sectionCard = "space-y-4 rounded-xl border border-border/80 bg-background p-4 md:p-5";
const scopeOptions = ["chat"] as const;
const entityTypes = ["CUSTOM_SECRET", "INTERNAL_CODE", "API_SECRET", "PHONE", "EMAIL", "CCCD", "PERSON", "ADDRESS", "ORG", "TAX_ID", "CREDIT_CARD", "OTHER"] as const;
const actionOptions = ["allow", "mask", "block"] as const;
const severityOptions = ["low", "medium", "high"] as const;
const matchModeOptions = ["strict_keyword", "keyword_plus_semantic"] as const;
const ragModeOptions = ["off", "explain", "verify"] as const;

function makeBuilderId(logic: BuilderLogic, index: number, type: BuilderRow["type"]) {
  return `cond_${logic}_${index}_${type}`;
}

function parseBuilder(conditions: Record<string, unknown> | undefined): {
  logic: BuilderLogic;
  rows: BuilderRow[];
  canBuild: boolean;
} {
  if (!conditions || typeof conditions !== "object") {
    return {
      logic: "any",
      rows: [
        {
          id: makeBuilderId("any", 0, "entity_match"),
          type: "entity_match",
          entityType: "CUSTOM_SECRET",
          minScore: "0.8",
          keywordsText: "",
        },
      ],
      canBuild: false,
    };
  }
  const logic: BuilderLogic = Array.isArray((conditions as { all?: unknown }).all) ? "all" : "any";
  const nodes = (conditions as { any?: unknown[]; all?: unknown[] })[logic];
  if (!Array.isArray(nodes)) {
    return {
      logic,
      rows: [
        {
          id: makeBuilderId(logic, 0, "entity_match"),
          type: "entity_match",
          entityType: "CUSTOM_SECRET",
          minScore: "0.8",
          keywordsText: "",
        },
      ],
      canBuild: false,
    };
  }
  const rows: BuilderRow[] = [];
  for (const [index, node] of nodes.entries()) {
    if (!node || typeof node !== "object" || Array.isArray(node)) {
      return {
        logic,
        rows: [
          {
            id: makeBuilderId(logic, 0, "entity_match"),
            type: "entity_match",
            entityType: "CUSTOM_SECRET",
            minScore: "0.8",
            keywordsText: "",
          },
        ],
        canBuild: false,
      };
    }
    const item = node as Record<string, unknown>;
    if (typeof item.entity_type === "string" && item.entity_type.trim()) {
      rows.push({
        id: makeBuilderId(logic, index, "entity_match"),
        type: "entity_match",
        entityType: item.entity_type.trim().toUpperCase(),
        minScore: item.min_score === undefined ? "0.8" : String(item.min_score),
        keywordsText: "",
      });
      continue;
    }
    if (item.signal && typeof item.signal === "object" && !Array.isArray(item.signal)) {
      const signal = item.signal as Record<string, unknown>;
      if (String(signal.field ?? "").trim() !== "context_keywords") {
        return {
          logic,
          rows: [
            {
              id: makeBuilderId(logic, 0, "entity_match"),
              type: "entity_match",
              entityType: "CUSTOM_SECRET",
              minScore: "0.8",
              keywordsText: "",
            },
          ],
          canBuild: false,
        };
      }
      const values = Array.isArray(signal.any_of)
        ? signal.any_of
            .map((x) => String(x ?? "").replace(/\r/g, ""))
            .filter((x) => x.trim().length > 0)
        : [];
      rows.push({
        id: makeBuilderId(logic, index, "signal_keyword_match"),
        type: "signal_keyword_match",
        entityType: "CUSTOM_SECRET",
        minScore: "0.8",
        keywordsText: values.join("\n"),
      });
      continue;
    }
    return {
      logic,
      rows: [
        {
          id: makeBuilderId(logic, 0, "entity_match"),
          type: "entity_match",
          entityType: "CUSTOM_SECRET",
          minScore: "0.8",
          keywordsText: "",
        },
      ],
      canBuild: false,
    };
  }
  return {
    logic,
    rows:
      rows.length > 0
        ? rows
        : [
            {
              id: makeBuilderId(logic, 0, "entity_match"),
              type: "entity_match",
              entityType: "CUSTOM_SECRET",
              minScore: "0.8",
              keywordsText: "",
            },
          ],
    canBuild: true,
  };
}

function buildConditions(logic: BuilderLogic, rows: BuilderRow[]) {
  return {
    [logic]: rows.map((row) =>
      row.type === "entity_match"
        ? {
            entity_type: row.entityType || "CUSTOM_SECRET",
            ...(row.minScore.trim() && Number.isFinite(Number(row.minScore))
              ? { min_score: Number(row.minScore) }
              : {}),
          }
        : {
            signal: {
              field: "context_keywords",
              any_of: row.keywordsText
                .split("\n")
                .map((x) => x.replace(/\r/g, ""))
                .filter((x) => x.trim().length > 0),
            },
          }
    ),
  } as Record<string, unknown>;
}

function jsonObject(value: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

export function DraftEditor({ draft, readOnly = false, validationError, onDraftChange }: DraftEditorProps) {
  const [logic, setLogic] = useState<BuilderLogic>("any");
  const [rows, setRows] = useState<BuilderRow[]>([]);
  const [canBuild, setCanBuild] = useState(true);
  const [conditionsJson, setConditionsJson] = useState("{}");
  const [conditionsError, setConditionsError] = useState<string | null>(null);
  const [ruleJson, setRuleJson] = useState("");
  const [termsJson, setTermsJson] = useState("");
  const [advancedError, setAdvancedError] = useState<string | null>(null);

  useEffect(() => {
    const parsed = parseBuilder(draft.rule.conditions);
    setLogic(parsed.logic);
    setRows(parsed.rows);
    setCanBuild(parsed.canBuild);
    setConditionsJson(JSON.stringify(draft.rule.conditions ?? {}, null, 2));
    setConditionsError(null);
    setRuleJson(JSON.stringify(draft.rule, null, 2));
    setTermsJson(JSON.stringify(draft.context_terms, null, 2));
    setAdvancedError(null);
  }, [draft]);

  const preview = useMemo(
    () =>
      rows.map((row) =>
        row.type === "entity_match"
          ? `Entity ${row.entityType} (min score ${row.minScore || "N/A"})`
          : `Signal keyword match with ${row.keywordsText.split("\n").map((x) => x.trim()).filter(Boolean).length} keyword(s)`
      ),
    [rows]
  );
  const scopeValue =
    draft.rule.scope && scopeOptions.includes(draft.rule.scope as (typeof scopeOptions)[number])
      ? draft.rule.scope
      : "chat";

  const updateRule = <K extends keyof SuggestionDraft["rule"]>(field: K, value: SuggestionDraft["rule"][K]) =>
    onDraftChange({ ...draft, rule: { ...draft.rule, [field]: value } });

  const commitRows = (nextLogic: BuilderLogic, nextRows: BuilderRow[]) => {
    const normalized =
      nextRows.length > 0
        ? nextRows
        : [
            {
              id: makeBuilderId(nextLogic, 0, "entity_match"),
              type: "entity_match",
              entityType: "CUSTOM_SECRET",
              minScore: "0.8",
              keywordsText: "",
            },
          ];
    const nextConditions = buildConditions(nextLogic, normalized);
    setLogic(nextLogic);
    setRows(normalized);
    setConditionsJson(JSON.stringify(nextConditions, null, 2));
    setConditionsError(null);
    updateRule("conditions", nextConditions);
  };

  const applyRawJson = () => {
    try {
      const nextRule = JSON.parse(ruleJson) as SuggestionDraft["rule"];
      const nextTerms = JSON.parse(termsJson) as SuggestionDraft["context_terms"];
      if (!nextRule || typeof nextRule !== "object" || Array.isArray(nextRule)) {
        setAdvancedError("Rule JSON must be an object.");
        return;
      }
      if (!Array.isArray(nextTerms)) {
        setAdvancedError("Context terms JSON must be an array.");
        return;
      }
      setAdvancedError(null);
      onDraftChange({ rule: nextRule, context_terms: nextTerms });
    } catch {
      setAdvancedError("Invalid JSON format in Advanced settings.");
    }
  };

  const syncConditionsJson = () => {
    const parsed = jsonObject(conditionsJson);
    if (!parsed) {
      setConditionsError("Conditions JSON must be a valid object.");
      return;
    }
    setConditionsError(null);
    updateRule("conditions", parsed);
    const rebuilt = parseBuilder(parsed);
    setLogic(rebuilt.logic);
    setRows(rebuilt.rows);
    setCanBuild(rebuilt.canBuild);
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

      <section className={sectionCard}>
        <h3 className="text-sm font-semibold text-foreground">Basic info</h3>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-1.5">
            <Label>Name</Label>
            <Input disabled={readOnly} onChange={(e) => updateRule("name", e.target.value)} value={draft.rule.name ?? ""} />
          </div>
          <div className="space-y-1.5 md:col-span-2">
            <Label>Description</Label>
            <Textarea disabled={readOnly} onChange={(e) => updateRule("description", e.target.value)} rows={3} value={draft.rule.description ?? ""} />
          </div>
        </div>
      </section>

      <section className={sectionCard}>
        <h3 className="text-sm font-semibold text-foreground">Behavior</h3>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label>Scope</Label>
            <select className={appSelectControlClassName} disabled={readOnly} onChange={(e) => updateRule("scope", e.target.value)} value={scopeValue}>
              {draft.rule.scope && !scopeOptions.includes(draft.rule.scope as (typeof scopeOptions)[number]) ? (
                <option value={draft.rule.scope}>{draft.rule.scope}</option>
              ) : null}
              {scopeOptions.map((x) => (
                <option key={x} value={x}>
                  {x}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label>Action</Label>
            <select className={appSelectControlClassName} disabled={readOnly} onChange={(e) => updateRule("action", e.target.value)} value={draft.rule.action ?? "mask"}>
              {actionOptions.map((x) => (
                <option key={x} value={x}>
                  {x}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label>Severity</Label>
            <select className={appSelectControlClassName} disabled={readOnly} onChange={(e) => updateRule("severity", e.target.value)} value={draft.rule.severity ?? "medium"}>
              {severityOptions.map((x) => (
                <option key={x} value={x}>
                  {x}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label>Match mode</Label>
            <select
              className={appSelectControlClassName}
              disabled={readOnly}
              onChange={(e) =>
                updateRule(
                  "match_mode",
                  e.target.value as SuggestionDraft["rule"]["match_mode"]
                )
              }
              value={draft.rule.match_mode ?? "strict_keyword"}
            >
              {matchModeOptions.map((x) => (
                <option key={x} value={x}>
                  {x}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label>RAG mode</Label>
            <select className={appSelectControlClassName} disabled={readOnly} onChange={(e) => updateRule("rag_mode", e.target.value)} value={draft.rule.rag_mode ?? "off"}>
              {ragModeOptions.map((x) => (
                <option key={x} value={x}>
                  {x}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label>Status</Label>
            <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border/80 bg-background px-3 py-2">
              <StatusBadge status={draft.rule.enabled ? "enabled" : "disabled"} />
              <label className="inline-flex items-center gap-2 text-sm text-foreground" htmlFor="draft-enabled">
                <input checked={Boolean(draft.rule.enabled)} className="h-4 w-4" disabled={readOnly} id="draft-enabled" onChange={(e) => updateRule("enabled", e.target.checked)} type="checkbox" />
                {draft.rule.enabled ? "Enabled" : "Disabled"}
              </label>
            </div>
          </div>
        </div>
      </section>

      <section className={sectionCard}>
        <h3 className="text-sm font-semibold text-foreground">Conditions</h3>
        <FieldHelpText>Mirrors RuleForm: logic, condition type, and signal keyword match.</FieldHelpText>
        {!canBuild ? (
          <AppAlert
            description="Current JSON uses structure outside the simple builder. Edit with Advanced JSON below."
            title="Builder unavailable"
            variant="warning"
          />
        ) : null}
        <div className="space-y-3 rounded-xl border border-border/80 bg-muted/10 p-3">
          <div className="space-y-1.5">
            <Label>Logic</Label>
            <select className={appSelectControlClassName} disabled={readOnly} onChange={(e) => commitRows(e.target.value as BuilderLogic, rows)} value={logic}>
              <option value="any">Match any conditions</option>
              <option value="all">Match all conditions</option>
            </select>
          </div>
          {rows.map((row, index) => (
            <div className="space-y-3 rounded-xl border border-border/80 bg-background p-3" key={row.id}>
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-medium">Condition #{index + 1}</p>
                <AppButton disabled={readOnly || rows.length <= 1} onClick={() => commitRows(logic, rows.filter((x) => x.id !== row.id))} size="sm" type="button" variant="secondary">
                  Remove
                </AppButton>
              </div>
              <div className="space-y-1.5">
                <Label>Condition type</Label>
                <select
                  className={appSelectControlClassName}
                  disabled={readOnly}
                  onChange={(e) => commitRows(logic, rows.map((x) => (x.id === row.id ? { ...x, type: e.target.value as BuilderRow["type"] } : x)))}
                  value={row.type}
                >
                  <option value="entity_match">Entity match</option>
                  <option value="signal_keyword_match">Signal keyword match</option>
                </select>
              </div>
              {row.type === "entity_match" ? (
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label>Entity type</Label>
                    <select className={appSelectControlClassName} disabled={readOnly} onChange={(e) => commitRows(logic, rows.map((x) => (x.id === row.id ? { ...x, entityType: e.target.value } : x)))} value={row.entityType}>
                      {entityTypes.map((x) => (
                        <option key={x} value={x}>
                          {x}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <Label>Minimum score</Label>
                    <Input disabled={readOnly} max="1" min="0" onChange={(e) => commitRows(logic, rows.map((x) => (x.id === row.id ? { ...x, minScore: e.target.value } : x)))} step="0.01" type="number" value={row.minScore} />
                  </div>
                </div>
              ) : (
                <div className="space-y-1.5">
                  <Label>Keywords (one per line)</Label>
                  <Textarea className="min-h-[100px]" disabled={readOnly} onChange={(e) => commitRows(logic, rows.map((x) => (x.id === row.id ? { ...x, keywordsText: e.target.value } : x)))} value={row.keywordsText} />
                </div>
              )}
            </div>
          ))}
          <div className="flex flex-wrap gap-2">
            <AppButton
              disabled={readOnly}
              onClick={() =>
                commitRows(logic, [
                  ...rows,
                  {
                    id: makeBuilderId(logic, rows.length, "entity_match"),
                    type: "entity_match",
                    entityType: "CUSTOM_SECRET",
                    minScore: "0.8",
                    keywordsText: "",
                  },
                ])
              }
              type="button"
              variant="secondary"
            >
              + Add entity condition
            </AppButton>
            <AppButton
              disabled={readOnly}
              onClick={() =>
                commitRows(logic, [
                  ...rows,
                  {
                    id: makeBuilderId(logic, rows.length, "signal_keyword_match"),
                    type: "signal_keyword_match",
                    entityType: "CUSTOM_SECRET",
                    minScore: "0.8",
                    keywordsText: "",
                  },
                ])
              }
              type="button"
              variant="secondary"
            >
              + Add signal condition
            </AppButton>
          </div>
          <div className="rounded-xl border border-border/80 bg-muted/20 p-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Preview</p>
            <div className="mt-1 space-y-1 text-sm text-foreground">
              {preview.map((line) => (
                <p key={line}>{line}</p>
              ))}
            </div>
          </div>
        </div>
        <details className="rounded-xl border border-dashed border-border/80 p-3 text-sm">
          <summary className="cursor-pointer font-medium text-foreground">Advanced conditions JSON</summary>
          <div className="mt-3 space-y-3">
            <Textarea className="min-h-[220px] font-mono text-xs" disabled={readOnly} onChange={(e) => setConditionsJson(e.target.value)} value={conditionsJson} />
            {conditionsError ? <InlineErrorText>{conditionsError}</InlineErrorText> : null}
            <div className="flex flex-wrap gap-2">
              <AppButton disabled={readOnly} onClick={() => setConditionsJson(JSON.stringify(buildConditions(logic, rows), null, 2))} size="sm" type="button" variant="secondary">Reset from builder</AppButton>
              <AppButton disabled={readOnly} onClick={syncConditionsJson} size="sm" type="button" variant="secondary">Sync JSON to builder</AppButton>
            </div>
          </div>
        </details>
      </section>

      <section className={sectionCard}>
        <h3 className="text-sm font-semibold text-foreground">Linked context terms</h3>
        <SuggestionContextTermsEditor readOnly={readOnly} terms={draft.context_terms} onChange={(nextTerms) => onDraftChange({ ...draft, context_terms: nextTerms })} />
      </section>

      <details className="rounded-xl border border-border/80 bg-muted/10 p-4 text-sm">
        <summary className="cursor-pointer font-medium text-foreground">Advanced settings</summary>
        <div className="mt-4 space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Stable key</Label>
              <Input disabled={readOnly} onChange={(e) => updateRule("stable_key", e.target.value)} value={draft.rule.stable_key ?? ""} />
            </div>
            <div className="space-y-1.5">
              <Label>Priority</Label>
              <Input disabled={readOnly} onChange={(e) => updateRule("priority", toNumber(e.target.value, 0))} type="number" value={draft.rule.priority ?? 0} />
            </div>
          </div>
          <div className="space-y-3 rounded-xl border border-border/80 bg-background p-4">
            <Label>Raw `draft.rule` JSON</Label>
            <Textarea className="min-h-[160px] font-mono text-xs" disabled={readOnly} onChange={(e) => setRuleJson(e.target.value)} value={ruleJson} />
            <Label>Raw `context_terms` JSON</Label>
            <Textarea className="min-h-[140px] font-mono text-xs" disabled={readOnly} onChange={(e) => setTermsJson(e.target.value)} value={termsJson} />
            {advancedError ? <InlineErrorText>{advancedError}</InlineErrorText> : null}
            <div className="flex justify-end">
              <AppButton disabled={readOnly} onClick={applyRawJson} size="sm" type="button" variant="secondary">
                Apply JSON to draft
              </AppButton>
            </div>
          </div>
        </div>
      </details>
    </div>
  );
}
