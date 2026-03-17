import { type ReactNode, useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Textarea } from "@/shared/ui/textarea";
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
    return { ok: true };
  }

  return {
    ok: false,
    message:
      "Unsupported conditions node. Use one of: any, all, not, entity_type, signal.",
  };
}

const ruleFormSchema = z.object({
  stable_key: z
    .string()
    .trim()
    .max(200, "Stable key must be <= 200 chars"),
  name: z.string().trim().min(1, "Name is required").max(300, "Name must be <= 300 chars"),
  description: z.string().max(2000, "Description must be <= 2000 chars").optional(),
  scope: z.enum(["prompt", "chat", "file", "api"]),
  action: z.enum(["allow", "mask", "block", "warn"]),
  severity: z.enum(["low", "medium", "high"]),
  priority: z.coerce.number().int().default(0),
  rag_mode: z.enum(["off", "explain", "verify"]),
  enabled: z.boolean().default(true),
  condition_type: z.enum(["entity_match"]),
  entity_type: z.string().trim().min(1, "Entity type is required"),
  min_score: z.coerce
    .number()
    .min(0, "Min score must be >= 0")
    .max(1, "Min score must be <= 1"),
  conditions_json: z
    .string()
    .min(2, "Conditions JSON is required")
    .refine((value) => {
      try {
        const parsed = JSON.parse(value);
        return typeof parsed === "object" && parsed !== null && !Array.isArray(parsed);
      } catch {
        return false;
      }
    }, "Conditions must be valid JSON object")
    .refine((value) => {
      try {
        const parsed = JSON.parse(value) as unknown;
        return validateConditionsNode(parsed).ok;
      } catch {
        return false;
      }
    }, "Conditions schema is invalid (expected any/all/not/entity_type/signal)."),
});

type RuleFormValues = z.infer<typeof ruleFormSchema>;

const scopeOptions = ["prompt", "chat", "file", "api"] as const;
const actionOptions = ["allow", "mask", "block", "warn"] as const;
const severityOptions = ["low", "medium", "high"] as const;
const ragModeOptions = ["off", "explain", "verify"] as const;
const entityTypeOptions = [
  "PHONE",
  "EMAIL",
  "CCCD",
  "PERSON",
  "ADDRESS",
  "ORG",
  "OTHER",
] as const;

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

const defaultConditionsJson = JSON.stringify(
  {
    any: [{ entity_type: "PHONE", min_score: 0.8 }],
  },
  null,
  2
);

type SimpleConditions = {
  conditionType: "entity_match";
  entityType: string;
  minScore: number;
};

function extractSimpleConditions(
  conditions: Record<string, unknown> | null | undefined
): SimpleConditions | null {
  if (!conditions || typeof conditions !== "object" || Array.isArray(conditions)) {
    return null;
  }

  const anyNode = (conditions as Record<string, unknown>).any;
  if (!Array.isArray(anyNode) || anyNode.length !== 1) {
    return null;
  }

  const first = anyNode[0];
  if (!first || typeof first !== "object" || Array.isArray(first)) {
    return null;
  }

  const item = first as Record<string, unknown>;
  const entityType = String(item.entity_type ?? "").trim();
  const minScoreRaw = item.min_score;
  const minScore =
    typeof minScoreRaw === "number"
      ? minScoreRaw
      : Number.parseFloat(String(minScoreRaw ?? "0"));

  if (!entityType || Number.isNaN(minScore)) {
    return null;
  }

  return {
    conditionType: "entity_match",
    entityType,
    minScore,
  };
}

function buildSimpleConditions(values: RuleFormValues): Record<string, unknown> {
  return {
    any: [
      {
        entity_type: values.entity_type.trim(),
        min_score: values.min_score,
      },
    ],
  };
}

export function RuleForm({
  mode,
  initialRule,
  isSubmitting = false,
  onCancel,
  onSubmit,
}: RuleFormProps) {
  const parsedSimpleConditions = useMemo(
    () => extractSimpleConditions(initialRule?.conditions),
    [initialRule?.conditions]
  );
  const [isAdvancedMode, setIsAdvancedMode] = useState(
    Boolean(initialRule && !parsedSimpleConditions)
  );

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
      condition_type: parsedSimpleConditions?.conditionType ?? "entity_match",
      entity_type: parsedSimpleConditions?.entityType ?? "PHONE",
      min_score: parsedSimpleConditions?.minScore ?? 0.8,
      conditions_json: initialRule?.conditions
        ? JSON.stringify(initialRule.conditions, null, 2)
        : defaultConditionsJson,
    }),
    [initialRule, parsedSimpleConditions]
  );

  const form = useForm<RuleFormValues>({
    resolver: zodResolver(ruleFormSchema),
    defaultValues,
  });

  useEffect(() => {
    form.reset(defaultValues);
  }, [defaultValues, form]);

  useEffect(() => {
    setIsAdvancedMode(Boolean(initialRule && !parsedSimpleConditions));
  }, [initialRule, parsedSimpleConditions]);

  const watchedEntityType = form.watch("entity_type");
  const watchedMinScore = form.watch("min_score");

  const simplePreview = useMemo(
    () =>
      JSON.stringify(
        buildSimpleConditions({
          ...defaultValues,
          entity_type: watchedEntityType,
          min_score: watchedMinScore,
        } as RuleFormValues),
        null,
        2
      ),
    [defaultValues, watchedEntityType, watchedMinScore]
  );

  const handleSubmit = form.handleSubmit(async (values) => {
    if (mode === "create" && !values.stable_key.trim()) {
      form.setError("stable_key", { message: "Stable key is required" });
      return;
    }

    const conditions = isAdvancedMode
      ? (JSON.parse(values.conditions_json) as Record<string, unknown>)
      : buildSimpleConditions(values);

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
      await onSubmit(payload);
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
    await onSubmit(payload);
  });

  const canEditAction = initialRule?.can_edit_action ?? true;
  const isUnsupportedSimpleMapping = Boolean(initialRule && !parsedSimpleConditions);

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      <div className="space-y-1.5">
        <Label htmlFor="stable_key">Stable key</Label>
        <Input
          disabled={mode === "edit"}
          id="stable_key"
          placeholder="personal.custom.sample.rule"
          {...form.register("stable_key")}
        />
        {mode === "edit" && (
          <p className="text-[11px] text-muted-foreground">
            Stable key is fixed after creation.
          </p>
        )}
        {form.formState.errors.stable_key && (
          <p className="text-xs text-destructive">{form.formState.errors.stable_key.message}</p>
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="name">Name</Label>
        <Input id="name" placeholder="Rule name" {...form.register("name")} />
        {form.formState.errors.name && (
          <p className="text-xs text-destructive">{form.formState.errors.name.message}</p>
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="description">Description</Label>
        <Textarea id="description" rows={2} {...form.register("description")} />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="scope">Scope</Label>
          <select
            className="h-10 w-full rounded-md border bg-background px-3 text-sm"
            id="scope"
            {...form.register("scope")}
          >
            <option value="prompt">prompt</option>
            <option value="chat">chat</option>
            <option value="file">file</option>
            <option value="api">api</option>
          </select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="action">Action</Label>
          <select
            className="h-10 w-full rounded-md border bg-background px-3 text-sm"
            disabled={!canEditAction && mode === "edit"}
            id="action"
            {...form.register("action")}
          >
            <option value="allow">allow</option>
            <option value="mask">mask</option>
            <option value="block">block</option>
            <option value="warn">warn</option>
          </select>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label htmlFor="severity">Severity</Label>
          <select
            className="h-10 w-full rounded-md border bg-background px-3 text-sm"
            id="severity"
            {...form.register("severity")}
          >
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
          </select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="priority">Priority</Label>
          <Input id="priority" type="number" {...form.register("priority")} />
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

      <div className="flex items-center gap-2">
        <input
          className="h-4 w-4"
          id="enabled"
          type="checkbox"
          {...form.register("enabled")}
        />
        <Label htmlFor="enabled">Enabled</Label>
      </div>

      <CardSection title="Conditions">
        <div className="space-y-1.5">
          <Label htmlFor="condition_type">Condition type</Label>
          <select
            className="h-10 w-full rounded-md border bg-background px-3 text-sm"
            disabled={isAdvancedMode}
            id="condition_type"
            {...form.register("condition_type")}
          >
            <option value="entity_match">Entity match</option>
          </select>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="entity_type">Entity type</Label>
            <select
              className="h-10 w-full rounded-md border bg-background px-3 text-sm"
              disabled={isAdvancedMode}
              id="entity_type"
              {...form.register("entity_type")}
            >
              {entityTypeOptions.map((entityType) => (
                <option key={entityType} value={entityType}>
                  {entityType}
                </option>
              ))}
            </select>
            {form.formState.errors.entity_type && (
              <p className="text-xs text-destructive">
                {form.formState.errors.entity_type.message}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="min_score">Min score</Label>
            <Input
              disabled={isAdvancedMode}
              id="min_score"
              max="1"
              min="0"
              step="0.01"
              type="number"
              {...form.register("min_score")}
            />
            {form.formState.errors.min_score && (
              <p className="text-xs text-destructive">
                {form.formState.errors.min_score.message}
              </p>
            )}
          </div>
        </div>

        <div className="rounded-md border bg-muted/30 p-2">
          <p className="mb-1 text-xs font-medium text-muted-foreground">
            Generated conditions (preview)
          </p>
          <pre className="overflow-auto text-xs">{simplePreview}</pre>
        </div>

        {isUnsupportedSimpleMapping && (
          <p className="text-xs text-muted-foreground">
            This rule uses advanced conditions format. Switch to Advanced JSON to edit
            full logic.
          </p>
        )}
      </CardSection>

      <div className="flex items-center justify-between rounded-md border border-dashed px-3 py-2">
        <p className="text-xs text-muted-foreground">
          Need full control? Use advanced JSON editor.
        </p>
        <Button
          onClick={() => {
            const nextValue = !isAdvancedMode;
            if (nextValue) {
              form.setValue("conditions_json", simplePreview, { shouldValidate: true });
            }
            setIsAdvancedMode(nextValue);
          }}
          size="sm"
          type="button"
          variant="outline"
        >
          {isAdvancedMode ? "Use simple mode" : "Advanced JSON"}
        </Button>
      </div>

      {isAdvancedMode && (
        <div className="space-y-1.5">
          <Label htmlFor="conditions_json">Raw conditions JSON</Label>
          <Textarea
            className="min-h-[220px] font-mono text-xs"
            id="conditions_json"
            {...form.register("conditions_json")}
          />
          <p className="text-[11px] text-muted-foreground">
            Supported DSL nodes: <code>any</code>, <code>all</code>, <code>not</code>,
            <code> entity_type</code>, <code>signal.field</code>.
          </p>
          {form.formState.errors.conditions_json && (
            <p className="text-xs text-destructive">
              {form.formState.errors.conditions_json.message}
            </p>
          )}
        </div>
      )}

      <div className="flex justify-end gap-2">
        <Button onClick={onCancel} type="button" variant="outline">
          Cancel
        </Button>
        <Button disabled={isSubmitting} type="submit">
          {isSubmitting ? "Saving..." : mode === "create" ? "Create Rule" : "Save Changes"}
        </Button>
      </div>
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
