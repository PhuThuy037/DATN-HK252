import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Textarea } from "@/shared/ui/textarea";
import { cn } from "@/shared/lib/utils";
import type { CreateRuleRequest, Rule, UpdateRuleRequest } from "@/features/rules/types";

function validateConditionsNode(node: unknown): { ok: boolean; message?: string } {
  if (!node || typeof node !== "object" || Array.isArray(node)) {
    return {
      ok: false,
      message: "Conditions root must be an object.",
    };
  }

  const objectNode = node as Record<string, unknown>;
  const keys = new Set(Object.keys(objectNode));
  const hasAny = keys.has("any");
  const hasAll = keys.has("all");
  const hasNot = keys.has("not");

  if (hasAny || hasAll || hasNot) {
    if (hasAny) {
      const children = objectNode.any;
      if (!Array.isArray(children)) {
        return { ok: false, message: "conditions.any must be an array." };
      }
      if (children.length === 0) {
        return { ok: false, message: "At least one condition is required." };
      }
      for (const child of children) {
        const childResult = validateConditionsNode(child);
        if (!childResult.ok) {
          return childResult;
        }
      }
      return { ok: true };
    }

    if (hasAll) {
      const children = objectNode.all;
      if (!Array.isArray(children)) {
        return { ok: false, message: "conditions.all must be an array." };
      }
      if (children.length === 0) {
        return { ok: false, message: "At least one condition is required." };
      }
      for (const child of children) {
        const childResult = validateConditionsNode(child);
        if (!childResult.ok) {
          return childResult;
        }
      }
      return { ok: true };
    }

    return validateConditionsNode(objectNode.not);
  }

  if (keys.has("entity_type")) {
    const entityType = String(objectNode.entity_type ?? "").trim();
    if (!entityType) {
      return { ok: false, message: "conditions.entity_type cannot be empty." };
    }
    return { ok: true };
  }

  if (keys.has("signal")) {
    const signal = objectNode.signal;
    if (!signal || typeof signal !== "object" || Array.isArray(signal)) {
      return { ok: false, message: "conditions.signal must be an object." };
    }
    const signalField = String((signal as Record<string, unknown>).field ?? "").trim();
    if (!signalField) {
      return { ok: false, message: "conditions.signal.field is required." };
    }
    const signalObject = signal as Record<string, unknown>;
    const operators = [
      "exists",
      "equals",
      "in",
      "contains",
      "startswith",
      "regex",
      "lt",
      "lte",
      "gt",
      "gte",
      "any_of",
      "all_of",
    ];
    const hasOperator = operators.some((operator) => operator in signalObject);
    if (!hasOperator) {
      return { ok: false, message: "conditions.signal requires at least one operator." };
    }
    for (const listOperator of ["in", "any_of", "all_of"] as const) {
      if (!(listOperator in signalObject)) {
        continue;
      }
      const raw = signalObject[listOperator];
      if (!Array.isArray(raw)) {
        return { ok: false, message: `conditions.signal.${listOperator} must be an array.` };
      }
      const cleaned = raw.map((value) => String(value ?? "").trim()).filter(Boolean);
      if (cleaned.length === 0) {
        return {
          ok: false,
          message: "At least one condition is required.",
        };
      }
    }
    return { ok: true };
  }

  return {
    ok: false,
    message: "Unsupported conditions node. Use one of: any, all, not, entity_type, signal.",
  };
}

const ruleFormSchema = z.object({
  stable_key: z
    .string()
    .trim()
    .min(1, "Stable key is required")
    .max(200, "Stable key must be <= 200 chars"),
  name: z.string().trim().min(1, "Name is required").max(300, "Name must be <= 300 chars"),
  description: z.string().max(2000, "Description must be <= 2000 chars").optional(),
  scope: z.enum(["prompt", "chat", "file", "api"]),
  action: z.enum(["allow", "mask", "block", "warn"]),
  severity: z.enum(["low", "medium", "high"]),
  priority: z.coerce
    .number()
    .refine((value) => Number.isFinite(value), "Priority must be a valid number")
    .int("Priority must be an integer")
    .min(-100000, "Priority must be between -100000 and 100000")
    .max(100000, "Priority must be between -100000 and 100000")
    .default(0),
  rag_mode: z.enum(["off", "explain", "verify"]),
  enabled: z.boolean().default(true),
});

type RuleFormValues = z.infer<typeof ruleFormSchema>;

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
const signalFieldOptions = ["context_keywords"] as const;

function getEnumValue<T extends readonly string[]>(
  options: T,
  value: string | null | undefined,
  fallback: T[number]
): T[number] {
  if (value && (options as readonly string[]).includes(value)) {
    return value as T[number];
  }
  return fallback;
}

type RuleFormProps = {
  mode: "create" | "edit";
  initialRule?: Rule | null;
  isSubmitting?: boolean;
  onCancel: () => void;
  onSubmit: (payload: CreateRuleRequest | UpdateRuleRequest) => Promise<void> | void;
};

type BuilderLogic = "any" | "all";
type BuilderConditionType = "entity_match" | "signal_keyword_match";

type BuilderCondition = {
  id: string;
  type: BuilderConditionType;
  entityType: string;
  minScore: string;
  signalField: string;
  keywordsText: string;
};

const STABLE_KEY_PATTERN = /^[a-z0-9]+(?:[._-][a-z0-9]+)*$/;
const MIN_PRIORITY = -100000;
const MAX_PRIORITY = 100000;

type RuleFieldErrorKey = keyof RuleFormValues | "conditions";

function mapFieldPathToFormKey(path: string): RuleFieldErrorKey | null {
  const normalized = String(path || "").trim().toLowerCase();
  if (!normalized) {
    return null;
  }
  if (normalized.includes("stable_key")) {
    return "stable_key";
  }
  if (normalized.includes("name")) {
    return "name";
  }
  if (normalized.includes("scope")) {
    return "scope";
  }
  if (normalized.includes("action")) {
    return "action";
  }
  if (normalized.includes("severity")) {
    return "severity";
  }
  if (normalized.includes("priority")) {
    return "priority";
  }
  if (normalized.includes("rag_mode")) {
    return "rag_mode";
  }
  if (normalized.includes("enabled")) {
    return "enabled";
  }
  if (normalized.includes("condition")) {
    return "conditions";
  }
  return null;
}

function mapFieldReasonToMessage(field: RuleFieldErrorKey, reason: string): string | null {
  const normalized = String(reason || "").trim().toLowerCase();
  if (!normalized) {
    return null;
  }

  if (field === "stable_key") {
    if (normalized.includes("global_rule_key_reserved")) {
      return "Stable key is reserved by a global rule.";
    }
    if (normalized.includes("exists") || normalized.includes("duplicate")) {
      return "Stable key already exists.";
    }
    if (normalized.includes("empty")) {
      return "Stable key is required";
    }
    if (normalized.includes("invalid_format")) {
      return "Stable key format is invalid. Use lowercase letters, numbers, dot, underscore, or dash.";
    }
  }

  if (field === "name" && normalized.includes("empty")) {
    return "Name is required";
  }
  if (field === "priority") {
    if (normalized.includes("int")) {
      return "Priority must be an integer";
    }
    if (normalized.includes("out_of_range")) {
      return `Priority must be between ${MIN_PRIORITY} and ${MAX_PRIORITY}`;
    }
    if (normalized.includes("finite") || normalized.includes("number")) {
      return "Priority must be a valid number";
    }
  }
  if (field === "scope" && normalized.includes("required")) {
    return "Scope is required";
  }
  if (field === "action" && normalized.includes("required")) {
    return "Action is required";
  }
  if (field === "severity" && normalized.includes("required")) {
    return "Severity is required";
  }
  if (field === "conditions") {
    if (
      normalized.includes("empty_list") ||
      normalized.includes("operator_required") ||
      normalized.includes("must_be_list")
    ) {
      return "At least one condition is required";
    }
    return "Conditions are invalid. Please check the builder/JSON structure.";
  }

  return null;
}

function extractRuleSubmitError(error: unknown): {
  fieldErrors: Partial<Record<RuleFieldErrorKey, string>>;
  message: string;
} {
  const fieldErrors: Partial<Record<RuleFieldErrorKey, string>> = {};
  const fallbackMessage =
    error instanceof Error && error.message ? error.message : "Failed to save rule.";

  const responseData =
    (error as { response?: { data?: unknown } } | null)?.response?.data ?? null;

  const envelopeError = (
    responseData && typeof responseData === "object"
      ? (responseData as { error?: { details?: unknown; message?: unknown } }).error
      : undefined
  ) as { details?: unknown; message?: unknown } | undefined;
  const envelopeDetails = Array.isArray(envelopeError?.details)
    ? envelopeError?.details
    : [];
  const defaultFieldMessage: Record<RuleFieldErrorKey, string> = {
    stable_key: "Stable key is invalid",
    name: "Name is invalid",
    description: "Description is invalid",
    scope: "Scope is invalid",
    action: "Action is invalid",
    severity: "Severity is invalid",
    priority: "Priority is invalid",
    rag_mode: "RAG mode is invalid",
    enabled: "Enabled value is invalid",
    conditions: "Conditions are invalid",
  };

  for (const detail of envelopeDetails) {
    if (!detail || typeof detail !== "object") {
      continue;
    }
    const row = detail as { field?: unknown; reason?: unknown };
    const key = mapFieldPathToFormKey(String(row.field ?? ""));
    if (!key) {
      continue;
    }
    const customMessage = mapFieldReasonToMessage(key, String(row.reason ?? ""));
    fieldErrors[key] = customMessage ?? defaultFieldMessage[key];
  }

  const fastApiDetails = Array.isArray(
    (responseData as { detail?: unknown } | null)?.detail
  )
    ? ((responseData as { detail?: unknown[] }).detail ?? [])
    : [];
  for (const detail of fastApiDetails) {
    if (!detail || typeof detail !== "object") {
      continue;
    }
    const row = detail as { loc?: unknown; msg?: unknown };
    const loc = Array.isArray(row.loc) ? row.loc.map((part) => String(part)).join(".") : "";
    const key = mapFieldPathToFormKey(loc);
    if (!key) {
      continue;
    }
    const msg = String(row.msg ?? "").trim();
    if (msg) {
      fieldErrors[key] = msg;
    }
  }

  const serverMessage =
    typeof envelopeError?.message === "string" && envelopeError.message.trim().length > 0
      ? envelopeError.message
      : fallbackMessage;

  return {
    fieldErrors,
    message: serverMessage,
  };
}

function normalizeEntityType(value: string | null | undefined): string {
  return String(value ?? "")
    .trim()
    .replace(/\s+/g, "_")
    .toUpperCase();
}

function parseJsonObject(value: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(value);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return null;
    }
    return parsed as Record<string, unknown>;
  } catch {
    return null;
  }
}

function makeConditionId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `cond_${Math.random().toString(16).slice(2, 10)}`;
}

function makeDefaultEntityCondition(entityType = "CUSTOM_SECRET", minScore = "0.8"): BuilderCondition {
  return {
    id: makeConditionId(),
    type: "entity_match",
    entityType: normalizeEntityType(entityType) || "CUSTOM_SECRET",
    minScore,
    signalField: "context_keywords",
    keywordsText: "",
  };
}

function makeDefaultSignalCondition(): BuilderCondition {
  return {
    id: makeConditionId(),
    type: "signal_keyword_match",
    entityType: "CUSTOM_SECRET",
    minScore: "0.8",
    signalField: "context_keywords",
    keywordsText: "",
  };
}

function builderConditionToJsonNode(condition: BuilderCondition): Record<string, unknown> {
  if (condition.type === "entity_match") {
    const normalizedType = normalizeEntityType(condition.entityType) || "CUSTOM_SECRET";
    const minScoreRaw = condition.minScore.trim();
    if (!minScoreRaw) {
      return { entity_type: normalizedType };
    }
    const minScore = Number.parseFloat(minScoreRaw);
    if (Number.isNaN(minScore)) {
      return { entity_type: normalizedType };
    }
    return {
      entity_type: normalizedType,
      min_score: minScore,
    };
  }

  const keywords = condition.keywordsText
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

  return {
    signal: {
      field: condition.signalField || "context_keywords",
      any_of: keywords,
    },
  };
}

function parseSupportedBuilderFromConditions(conditions: unknown): {
  canParseRoot: boolean;
  logic: BuilderLogic;
  conditions: BuilderCondition[];
  unsupportedNodes: unknown[];
} {
  if (!conditions || typeof conditions !== "object" || Array.isArray(conditions)) {
    return {
      canParseRoot: false,
      logic: "any",
      conditions: [],
      unsupportedNodes: [],
    };
  }

  const root = conditions as Record<string, unknown>;
  const hasAny = Array.isArray(root.any);
  const hasAll = Array.isArray(root.all);
  if (!hasAny && !hasAll) {
    return {
      canParseRoot: false,
      logic: "any",
      conditions: [],
      unsupportedNodes: [],
    };
  }

  const logic: BuilderLogic = hasAll ? "all" : "any";
  const items = (root[logic] as unknown[]) ?? [];
  const mapped: BuilderCondition[] = [];
  const unsupportedNodes: unknown[] = [];

  for (const item of items) {
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      unsupportedNodes.push(item);
      continue;
    }

    const node = item as Record<string, unknown>;

    if (typeof node.entity_type === "string" && node.entity_type.trim()) {
      const minScore =
        node.min_score === undefined || node.min_score === null ? "0.8" : String(node.min_score);
      mapped.push(makeDefaultEntityCondition(node.entity_type, minScore));
      continue;
    }

    const signalNode = node.signal;
    if (signalNode && typeof signalNode === "object" && !Array.isArray(signalNode)) {
      const signal = signalNode as Record<string, unknown>;
      const field = String(signal.field ?? "").trim();
      const rawAnyOf = signal.any_of;
      const anyOf = Array.isArray(rawAnyOf)
        ? rawAnyOf.map((value) => String(value ?? "").trim()).filter(Boolean)
        : [];

      if (field === "context_keywords") {
        const signalCondition = makeDefaultSignalCondition();
        signalCondition.signalField = field;
        signalCondition.keywordsText = anyOf.join("\n");
        mapped.push(signalCondition);
        continue;
      }
    }

    unsupportedNodes.push(item);
  }

  return {
    canParseRoot: true,
    logic,
    conditions: mapped,
    unsupportedNodes,
  };
}

function buildConditionsJsonFromBuilder(
  logic: BuilderLogic,
  conditions: BuilderCondition[],
  unsupportedNodes: unknown[]
): Record<string, unknown> {
  const builderNodes = conditions.map(builderConditionToJsonNode);
  return {
    [logic]: [...builderNodes, ...unsupportedNodes],
  };
}

function getHumanReadablePreview(
  logic: BuilderLogic,
  conditions: BuilderCondition[],
  unsupportedCount: number
): string[] {
  if (conditions.length === 0 && unsupportedCount === 0) {
    return ["No conditions configured yet."];
  }

  const lines: string[] = [];
  lines.push(`This rule triggers when matching ${logic === "any" ? "any" : "all"} condition(s):`);

  for (const condition of conditions) {
    if (condition.type === "entity_match") {
      const minScore = condition.minScore.trim();
      if (minScore) {
        lines.push(`- entity is ${normalizeEntityType(condition.entityType)} with min score ${minScore}`);
      } else {
        lines.push(`- entity is ${normalizeEntityType(condition.entityType)}`);
      }
      continue;
    }

    const keywords = condition.keywordsText
      .split("\n")
      .map((value) => value.trim())
      .filter(Boolean);

    if (keywords.length === 0) {
      lines.push(`- ${condition.signalField} has at least one matching keyword`);
    } else {
      const quoted = keywords.map((keyword) => `"${keyword}"`).join(", ");
      lines.push(`- ${condition.signalField} matches keyword ${quoted}`);
    }
  }

  if (unsupportedCount > 0) {
    lines.push(`- plus ${unsupportedCount} advanced condition node(s) preserved in JSON`);
  }

  return lines;
}

function validateBuilderConditions(
  conditions: BuilderCondition[],
  unsupportedCount: number
): string | null {
  if (conditions.length === 0 && unsupportedCount === 0) {
    return "At least one condition is required.";
  }

  for (const condition of conditions) {
    if (condition.type === "entity_match") {
      const entityType = normalizeEntityType(condition.entityType);
      if (!entityType) {
        return "Entity type is required.";
      }
      const minScoreRaw = condition.minScore.trim();
      if (minScoreRaw.length > 0) {
        const minScore = Number.parseFloat(minScoreRaw);
        if (Number.isNaN(minScore) || minScore < 0 || minScore > 1) {
          return "Min score must be a number between 0 and 1.";
        }
      }
      continue;
    }

    const keywords = condition.keywordsText
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
    if (keywords.length === 0) {
      return "At least one condition is required.";
    }
  }

  return null;
}

export function RuleForm({
  mode,
  initialRule,
  isSubmitting = false,
  onCancel,
  onSubmit,
}: RuleFormProps) {
  const defaultValues = useMemo<RuleFormValues>(
    () => ({
      stable_key: initialRule?.stable_key ?? "",
      name: initialRule?.name ?? "",
      description: initialRule?.description ?? "",
      scope: getEnumValue(scopeOptions, initialRule?.scope, "prompt"),
      action: getEnumValue(actionOptions, initialRule?.action, "mask"),
      severity: getEnumValue(severityOptions, initialRule?.severity, "medium"),
      priority: initialRule?.priority ?? 0,
      rag_mode: getEnumValue(ragModeOptions, initialRule?.rag_mode, "off"),
      enabled: initialRule?.enabled ?? true,
    }),
    [initialRule]
  );

  const form = useForm<RuleFormValues>({
    resolver: zodResolver(ruleFormSchema),
    defaultValues,
  });

  const [builderLogic, setBuilderLogic] = useState<BuilderLogic>("any");
  const [builderConditions, setBuilderConditions] = useState<BuilderCondition[]>([
    makeDefaultEntityCondition(),
  ]);
  const [unsupportedNodes, setUnsupportedNodes] = useState<unknown[]>([]);

  const [showAdvancedJson, setShowAdvancedJson] = useState(false);
  const [advancedJsonText, setAdvancedJsonText] = useState<string>(
    JSON.stringify({ any: [builderConditionToJsonNode(makeDefaultEntityCondition())] }, null, 2)
  );
  const [advancedJsonError, setAdvancedJsonError] = useState<string | null>(null);
  const [advancedModeWarning, setAdvancedModeWarning] = useState<string | null>(null);
  const [saveFromAdvancedJson, setSaveFromAdvancedJson] = useState(false);
  const [isBuilderAvailable, setIsBuilderAvailable] = useState(true);
  const [conditionsError, setConditionsError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [hasSubmitted, setHasSubmitted] = useState(false);

  useEffect(() => {
    form.reset(defaultValues);

    const initialConditions = initialRule?.conditions ?? {
      any: [{ entity_type: "CUSTOM_SECRET", min_score: 0.8 }],
    };

    const parseResult = parseSupportedBuilderFromConditions(initialConditions);
    if (parseResult.canParseRoot) {
      setIsBuilderAvailable(true);
      setBuilderLogic(parseResult.logic);
      setBuilderConditions(
        parseResult.conditions.length > 0
          ? parseResult.conditions
          : [makeDefaultEntityCondition()]
      );
      setUnsupportedNodes(parseResult.unsupportedNodes);
      setSaveFromAdvancedJson(false);
      setAdvancedModeWarning(
        parseResult.unsupportedNodes.length > 0
          ? "Some advanced nodes are preserved and can be edited in Advanced JSON."
          : null
      );
    } else {
      setIsBuilderAvailable(false);
      setBuilderLogic("any");
      setBuilderConditions([makeDefaultEntityCondition()]);
      setUnsupportedNodes([]);
      setSaveFromAdvancedJson(Boolean(initialRule?.conditions));
      setAdvancedModeWarning(
        initialRule?.conditions
          ? "Current conditions are not fully supported by builder. Use Advanced JSON for full editing."
          : null
      );
    }

    setShowAdvancedJson(false);
    setAdvancedJsonText(JSON.stringify(initialConditions, null, 2));
    setAdvancedJsonError(null);
    setConditionsError(null);
    setSubmitError(null);
    setHasSubmitted(false);
  }, [defaultValues, form, initialRule]);

  useEffect(() => {
    if (!hasSubmitted) {
      return;
    }

    const errorKeys = Object.keys(form.formState.errors) as Array<keyof RuleFormValues>;
    if (errorKeys.length > 0) {
      const firstKey = errorKeys[0];
      const target = document.getElementById(String(firstKey));
      target?.scrollIntoView({ behavior: "smooth", block: "center" });
      form.setFocus(firstKey);
      return;
    }

    if (conditionsError) {
      const target = document.getElementById("conditions-section");
      target?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [hasSubmitted, form, form.formState.errors, conditionsError]);

  const generatedConditionsJsonObject = useMemo(
    () => buildConditionsJsonFromBuilder(builderLogic, builderConditions, unsupportedNodes),
    [builderConditions, builderLogic, unsupportedNodes]
  );

  const generatedConditionsJsonString = useMemo(
    () => JSON.stringify(generatedConditionsJsonObject, null, 2),
    [generatedConditionsJsonObject]
  );

  const humanPreviewLines = useMemo(
    () => getHumanReadablePreview(builderLogic, builderConditions, unsupportedNodes.length),
    [builderConditions, builderLogic, unsupportedNodes.length]
  );

  const addCondition = (type: BuilderConditionType) => {
    setBuilderConditions((previous) => [
      ...previous,
      type === "entity_match" ? makeDefaultEntityCondition() : makeDefaultSignalCondition(),
    ]);
  };

  const updateCondition = (id: string, patch: Partial<BuilderCondition>) => {
    setBuilderConditions((previous) =>
      previous.map((condition) => {
        if (condition.id !== id) {
          return condition;
        }
        const next = { ...condition, ...patch };
        if (patch.type && patch.type !== condition.type) {
          if (patch.type === "entity_match") {
            return {
              ...next,
              entityType: condition.entityType || "CUSTOM_SECRET",
              minScore: condition.minScore || "0.8",
            };
          }
          return {
            ...next,
            signalField: "context_keywords",
            keywordsText: condition.keywordsText || "",
          };
        }
        return next;
      })
    );
  };

  const removeCondition = (id: string) => {
    setBuilderConditions((previous) => previous.filter((condition) => condition.id !== id));
  };

  const toggleAdvancedJson = () => {
    const next = !showAdvancedJson;
    setShowAdvancedJson(next);
    if (next && !saveFromAdvancedJson) {
      setAdvancedJsonText(generatedConditionsJsonString);
    }
  };

  const syncJsonToBuilder = () => {
    const parsed = parseJsonObject(advancedJsonText);
    if (!parsed) {
      setAdvancedJsonError("Conditions JSON must be a valid JSON object.");
      setSaveFromAdvancedJson(true);
      return;
    }

    const validation = validateConditionsNode(parsed);
    if (!validation.ok) {
      setAdvancedJsonError(validation.message ?? "Conditions schema is invalid.");
      setSaveFromAdvancedJson(true);
      return;
    }

    const parseResult = parseSupportedBuilderFromConditions(parsed);
    if (parseResult.canParseRoot) {
      setIsBuilderAvailable(true);
      setBuilderLogic(parseResult.logic);
      setBuilderConditions(
        parseResult.conditions.length > 0
          ? parseResult.conditions
          : [makeDefaultEntityCondition()]
      );
      setUnsupportedNodes(parseResult.unsupportedNodes);
      setAdvancedJsonError(null);
      setSaveFromAdvancedJson(false);
      setAdvancedModeWarning(
        parseResult.unsupportedNodes.length > 0
          ? "Some advanced nodes are preserved and can be edited in Advanced JSON."
          : null
      );
      return;
    }

    setAdvancedJsonError(null);
    setSaveFromAdvancedJson(true);
    setIsBuilderAvailable(false);
    setAdvancedModeWarning(
      "JSON is valid but outside builder support. Rule will be saved from Advanced JSON."
    );
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setHasSubmitted(true);
    setSubmitError(null);
    setConditionsError(null);
    setAdvancedJsonError(null);
    form.clearErrors();

    const isValid = await form.trigger(undefined, { shouldFocus: true });
    if (!isValid) {
      setSubmitError("Please fix the highlighted fields before saving.");
      return;
    }

    const values = form.getValues();

    if (mode === "create") {
      const stableKey = values.stable_key.trim();
      if (!STABLE_KEY_PATTERN.test(stableKey)) {
        form.setError("stable_key", {
          message:
            "Stable key format is invalid. Use lowercase letters, numbers, dot, underscore, or dash.",
        });
        form.setFocus("stable_key");
        return;
      }
    }

    let conditions: Record<string, unknown>;
    if (saveFromAdvancedJson || !isBuilderAvailable) {
      const parsed = parseJsonObject(advancedJsonText);
      if (!parsed) {
        setConditionsError("Conditions JSON must be a valid JSON object.");
        setAdvancedJsonError("Conditions JSON must be a valid JSON object.");
        return;
      }

      const validation = validateConditionsNode(parsed);
      if (!validation.ok) {
        const message = validation.message ?? "Conditions schema is invalid.";
        setConditionsError(message);
        setAdvancedJsonError(message);
        return;
      }

      const parseResult = parseSupportedBuilderFromConditions(parsed);
      if (parseResult.canParseRoot) {
        setIsBuilderAvailable(true);
        setBuilderLogic(parseResult.logic);
        setBuilderConditions(
          parseResult.conditions.length > 0
            ? parseResult.conditions
            : [makeDefaultEntityCondition()]
        );
        setUnsupportedNodes(parseResult.unsupportedNodes);
        setSaveFromAdvancedJson(false);
      }

      conditions = parsed;
    } else {
      const builderValidationMessage = validateBuilderConditions(
        builderConditions,
        unsupportedNodes.length
      );
      if (builderValidationMessage) {
        setConditionsError(builderValidationMessage);
        return;
      }
      conditions = generatedConditionsJsonObject;
    }

    if (mode === "create") {
      const payload: CreateRuleRequest = {
        stable_key: values.stable_key.trim(),
        name: values.name.trim(),
        description: values.description?.trim() || null,
        scope: values.scope,
        action: values.action,
        severity: values.severity,
        priority: values.priority,
        rag_mode: values.rag_mode,
        enabled: values.enabled,
        conditions,
      };
      try {
        await onSubmit(payload);
      } catch (error) {
        const parsedError = extractRuleSubmitError(error);
        for (const [key, message] of Object.entries(parsedError.fieldErrors)) {
          if (!message) {
            continue;
          }
          if (key === "conditions") {
            setConditionsError(message);
            continue;
          }
          form.setError(key as keyof RuleFormValues, { message });
        }
        setSubmitError(parsedError.message);
      }
      return;
    }

    const payload: UpdateRuleRequest = {
      name: values.name.trim(),
      description: values.description?.trim() || null,
      scope: values.scope,
      action: values.action,
      severity: values.severity,
      priority: values.priority,
      rag_mode: values.rag_mode,
      enabled: values.enabled,
      conditions,
    };
    try {
      await onSubmit(payload);
    } catch (error) {
      const parsedError = extractRuleSubmitError(error);
      for (const [key, message] of Object.entries(parsedError.fieldErrors)) {
        if (!message) {
          continue;
        }
        if (key === "conditions") {
          setConditionsError(message);
          continue;
        }
        form.setError(key as keyof RuleFormValues, { message });
      }
      setSubmitError(parsedError.message);
    }
  };

  const canEditAction = initialRule?.can_edit_action ?? true;
  const hasFieldErrors = Object.keys(form.formState.errors).length > 0 || Boolean(conditionsError);
  const showErrorSummary = hasSubmitted && (hasFieldErrors || Boolean(submitError));

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      {showErrorSummary && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <p className="font-medium">Please review the form errors.</p>
          {submitError && <p className="mt-1 text-xs">{submitError}</p>}
        </div>
      )}
      <div className="space-y-1.5">
        <Label htmlFor="stable_key">
          Stable key <span className="text-destructive">*</span>
        </Label>
        <Input
          className={cn(form.formState.errors.stable_key && "border-destructive focus-visible:ring-destructive")}
          disabled={mode === "edit"}
          id="stable_key"
          maxLength={200}
          pattern={mode === "create" ? STABLE_KEY_PATTERN.source : undefined}
          placeholder="personal.custom.sample.rule"
          required={mode === "create"}
          title="Use lowercase letters, numbers, dot, underscore, or dash."
          {...form.register("stable_key")}
        />
        {mode === "edit" && (
          <p className="text-[11px] text-muted-foreground">Stable key is fixed after creation.</p>
        )}
        {form.formState.errors.stable_key && (
          <p className="text-xs text-destructive">{form.formState.errors.stable_key.message}</p>
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="name">
          Name <span className="text-destructive">*</span>
        </Label>
        <Input
          className={cn(form.formState.errors.name && "border-destructive focus-visible:ring-destructive")}
          id="name"
          maxLength={300}
          placeholder="Rule name"
          required
          {...form.register("name")}
        />
        {form.formState.errors.name && (
          <p className="text-xs text-destructive">{form.formState.errors.name.message}</p>
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="description">Description</Label>
        <Textarea id="description" maxLength={2000} rows={2} {...form.register("description")} />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="scope">
            Scope <span className="text-destructive">*</span>
          </Label>
          <select
            className={cn(
              "h-10 w-full rounded-md border bg-background px-3 text-sm",
              form.formState.errors.scope && "border-destructive"
            )}
            id="scope"
            required
            {...form.register("scope")}
          >
            <option value="prompt">prompt</option>
            <option value="chat">chat</option>
            <option value="file">file</option>
            <option value="api">api</option>
          </select>
          {form.formState.errors.scope && (
            <p className="text-xs text-destructive">{form.formState.errors.scope.message}</p>
          )}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="action">
            Action <span className="text-destructive">*</span>
          </Label>
          <select
            className={cn(
              "h-10 w-full rounded-md border bg-background px-3 text-sm",
              form.formState.errors.action && "border-destructive"
            )}
            disabled={!canEditAction && mode === "edit"}
            id="action"
            required
            {...form.register("action")}
          >
            <option value="allow">allow</option>
            <option value="mask">mask</option>
            <option value="block">block</option>
            <option value="warn">warn</option>
          </select>
          {form.formState.errors.action && (
            <p className="text-xs text-destructive">{form.formState.errors.action.message}</p>
          )}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label htmlFor="severity">
            Severity <span className="text-destructive">*</span>
          </Label>
          <select
            className={cn(
              "h-10 w-full rounded-md border bg-background px-3 text-sm",
              form.formState.errors.severity && "border-destructive"
            )}
            id="severity"
            required
            {...form.register("severity")}
          >
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
          </select>
          {form.formState.errors.severity && (
            <p className="text-xs text-destructive">{form.formState.errors.severity.message}</p>
          )}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="priority">
            Priority <span className="text-destructive">*</span>
          </Label>
          <Input
            className={cn(form.formState.errors.priority && "border-destructive focus-visible:ring-destructive")}
            id="priority"
            max={MAX_PRIORITY}
            min={MIN_PRIORITY}
            required
            type="number"
            {...form.register("priority")}
          />
          {form.formState.errors.priority && (
            <p className="text-xs text-destructive">{form.formState.errors.priority.message}</p>
          )}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="rag_mode">RAG mode</Label>
          <select
            className="h-10 w-full rounded-md border bg-background px-3 text-sm"
            id="rag_mode"
            {...form.register("rag_mode")}
          >
            <option value="off">off</option>
            <option value="explain">explain</option>
            <option value="verify">verify</option>
          </select>
        </div>
      </div>

      <div className="inline-flex items-center gap-2 rounded-md border px-3 py-2">
        <input
          className="h-4 w-4 shrink-0 align-middle"
          id="enabled"
          type="checkbox"
          {...form.register("enabled")}
        />
        <Label className="cursor-pointer leading-none" htmlFor="enabled">
          Enabled
        </Label>
      </div>

      <div id="conditions-section">
      <CardSection title="Conditions">
        <p className="text-xs text-muted-foreground">
          Required <span className="text-destructive">*</span>
        </p>
        {isBuilderAvailable ? (
          <>
            <div className="space-y-1.5">
              <Label htmlFor="conditions_logic">Logic</Label>
              <select
                className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                id="conditions_logic"
                onChange={(event) => setBuilderLogic(event.target.value as BuilderLogic)}
                value={builderLogic}
              >
                <option value="any">Match any conditions</option>
                <option value="all">Match all conditions</option>
              </select>
            </div>

            {builderConditions.map((condition, index) => (
              <div className="space-y-3 rounded-md border p-3" key={condition.id}>
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium">Condition #{index + 1}</p>
                  <Button
                    disabled={builderConditions.length <= 1}
                    onClick={() => removeCondition(condition.id)}
                    size="sm"
                    type="button"
                    variant="outline"
                  >
                    Remove
                  </Button>
                </div>

                <div className="space-y-1.5">
                  <Label>Type</Label>
                  <select
                    className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                    onChange={(event) =>
                      updateCondition(condition.id, {
                        type: event.target.value as BuilderConditionType,
                      })
                    }
                    value={condition.type}
                  >
                    <option value="entity_match">Entity match</option>
                    <option value="signal_keyword_match">Signal keyword match</option>
                  </select>
                </div>

                {condition.type === "entity_match" && (
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label>Entity type</Label>
                      <select
                        className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                        onChange={(event) =>
                          updateCondition(condition.id, { entityType: event.target.value })
                        }
                        value={normalizeEntityType(condition.entityType)}
                      >
                        {entityTypeOptions.map((entityType) => (
                          <option key={entityType} value={entityType}>
                            {entityType}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="space-y-1.5">
                      <Label>Min score</Label>
                      <Input
                        max="1"
                        min="0"
                        onChange={(event) =>
                          updateCondition(condition.id, { minScore: event.target.value })
                        }
                        placeholder="0.8"
                        step="0.01"
                        type="number"
                        value={condition.minScore}
                      />
                    </div>
                  </div>
                )}

                {condition.type === "signal_keyword_match" && (
                  <div className="space-y-3">
                    <div className="space-y-1.5">
                      <Label>Signal field</Label>
                      <select
                        className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                        onChange={(event) =>
                          updateCondition(condition.id, { signalField: event.target.value })
                        }
                        value={condition.signalField}
                      >
                        {signalFieldOptions.map((signalField) => (
                          <option key={signalField} value={signalField}>
                            {signalField}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="space-y-1.5">
                      <Label>Keywords (one per line)</Label>
                      <Textarea
                        className="min-h-[100px]"
                        onChange={(event) =>
                          updateCondition(condition.id, { keywordsText: event.target.value })
                        }
                        placeholder="dt-thuy-1234"
                        value={condition.keywordsText}
                      />
                    </div>
                  </div>
                )}
              </div>
            ))}

            <div className="flex flex-wrap gap-2">
              <Button onClick={() => addCondition("entity_match")} type="button" variant="outline">
                + Add entity condition
              </Button>
              <Button
                onClick={() => addCondition("signal_keyword_match")}
                type="button"
                variant="outline"
              >
                + Add signal condition
              </Button>
            </div>

            <div className="rounded-md border bg-muted/30 p-3">
              <p className="text-xs font-medium text-muted-foreground">Human-readable preview</p>
              <div className="mt-2 space-y-1 text-sm">
                {humanPreviewLines.map((line) => (
                  <p key={line}>{line}</p>
                ))}
              </div>
            </div>
          </>
        ) : (
          <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            Builder cannot represent current JSON safely. Use Advanced JSON, then click{" "}
            <span className="font-medium">Sync JSON to builder</span> after simplifying structure.
          </div>
        )}

        {advancedModeWarning && (
          <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            {advancedModeWarning}
          </div>
        )}

        <div className="space-y-2 rounded-md border border-dashed p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs text-muted-foreground">Advanced mode for raw JSON editing.</p>
            <Button onClick={toggleAdvancedJson} size="sm" type="button" variant="outline">
              {showAdvancedJson ? "Hide advanced JSON" : "Show advanced JSON"}
            </Button>
          </div>

          {showAdvancedJson && (
            <div className="space-y-2">
              <Textarea
                className="min-h-[220px] font-mono text-xs"
                onChange={(event) => {
                  setAdvancedJsonText(event.target.value);
                  setSaveFromAdvancedJson(true);
                  setAdvancedJsonError(null);
                }}
                value={advancedJsonText}
              />
              {advancedJsonError && <p className="text-xs text-destructive">{advancedJsonError}</p>}
              <div className="flex flex-wrap gap-2">
                <Button
                  onClick={() => {
                    setAdvancedJsonText(generatedConditionsJsonString);
                    setSaveFromAdvancedJson(false);
                    setAdvancedJsonError(null);
                    setIsBuilderAvailable(true);
                  }}
                  size="sm"
                  type="button"
                  variant="outline"
                >
                  Reset JSON from builder
                </Button>
                <Button onClick={syncJsonToBuilder} size="sm" type="button" variant="outline">
                  Sync JSON to builder
                </Button>
              </div>
            </div>
          )}
        </div>

        <details className="rounded-md border p-2">
          <summary className="cursor-pointer text-xs text-muted-foreground">
            Preview generated JSON
          </summary>
          <pre className="mt-2 overflow-auto rounded bg-muted p-2 text-xs">
            {generatedConditionsJsonString}
          </pre>
        </details>
        {conditionsError && <p className="text-xs text-destructive">{conditionsError}</p>}
      </CardSection>
      </div>

      <div className="flex justify-end gap-2">
        <Button onClick={onCancel} type="button" variant="outline">
          Cancel
        </Button>
        <Button disabled={isSubmitting} type="submit">
          {isSubmitting ? "Saving..." : mode === "create" ? "Create Rule" : "Save Changes"}
        </Button>
      </div>
      {submitError && !showErrorSummary && <p className="text-xs text-destructive">{submitError}</p>}
    </form>
  );
}

function CardSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-3 rounded-md border p-3">
      <h4 className="text-sm font-medium">{title}</h4>
      {children}
    </div>
  );
}
