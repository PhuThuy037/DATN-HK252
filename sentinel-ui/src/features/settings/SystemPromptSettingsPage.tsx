import { Sparkles, Shield, TestTubeDiagonal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useMyRuleSets } from "@/features/rules/hooks";
import {
  useSystemPrompt,
  useUpdateSystemPrompt,
} from "@/features/settings/hooks";
import { cn } from "@/shared/lib/utils";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppButton } from "@/shared/ui/app-button";
import { AppLoadingState } from "@/shared/ui/app-loading-state";
import { AppPageHeader } from "@/shared/ui/app-page-header";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { appActionRowClassName } from "@/shared/ui/design-tokens";
import { FieldHelpText } from "@/shared/ui/field-help-text";
import { Label } from "@/shared/ui/label";
import { StatusBadge } from "@/shared/ui/status-badge";
import { Textarea } from "@/shared/ui/textarea";
import { toast } from "@/shared/ui/use-toast";

const DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant.";
const TEST_PROMPT_PLACEHOLDER =
  "Example: A user asks for a production API key or internal credentials.";

type StatusTone = "primary" | "success" | "warning" | "danger" | "muted";

const behaviorTemplates: Array<{
  label: string;
  description: string;
  tone: StatusTone;
  testPrompt: string;
  value: string;
}> = [
  {
    label: "Friendly",
    description: "Warm, clear, and approachable responses for everyday support.",
    tone: "primary",
    testPrompt: "Explain our password reset process to a non-technical customer.",
    value: [
      "You are a warm, approachable assistant for this workspace.",
      "Answer in clear plain language, stay calm and helpful, and keep responses concise.",
      "Ask a brief clarifying question only when it is truly needed, otherwise make the safest reasonable assumption and say so.",
    ].join("\n"),
  },
  {
    label: "Strict compliance",
    description: "Prioritize policy adherence, refusals, and explicit boundary keeping.",
    tone: "warning",
    testPrompt: "A user asks for guidance that may conflict with company policy.",
    value: [
      "You are a compliance-first assistant for this workspace.",
      "Follow workspace rules and policy boundaries exactly.",
      "Do not speculate, do not bypass restrictions, and clearly refuse disallowed requests.",
      "If key policy context is missing, explain what is missing and ask for the minimum clarification needed.",
    ].join("\n"),
  },
  {
    label: "Security-focused",
    description: "Protect secrets, internal data, and risky operational details by default.",
    tone: "danger",
    testPrompt: "A user asks to reveal live credentials from an internal system.",
    value: [
      "You are a security-focused assistant for this workspace.",
      "Prioritize protecting secrets, credentials, internal systems, customer data, and sensitive operational details.",
      "Refuse requests that would expose sensitive information or weaken security controls.",
      "When possible, offer a safer alternative and choose the more conservative response when in doubt.",
    ].join("\n"),
  },
];

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

function includesAny(value: string, keywords: string[]) {
  return keywords.some((keyword) => value.includes(keyword));
}

function getBehaviorSignals(prompt: string) {
  const normalized = prompt.trim().toLowerCase();
  const signals: Array<{ label: string; description: string; tone: StatusTone }> = [];

  if (
    includesAny(normalized, [
      "warm",
      "friendly",
      "approachable",
      "empathetic",
      "plain language",
      "helpful",
    ])
  ) {
    signals.push({
      label: "Friendly tone",
      description: "The draft emphasizes approachable communication.",
      tone: "primary",
    });
  }

  if (
    includesAny(normalized, [
      "compliance",
      "policy",
      "boundaries",
      "refuse",
      "disallowed",
      "rules",
    ])
  ) {
    signals.push({
      label: "Compliance guardrails",
      description: "The draft calls out policy limits and refusal behavior.",
      tone: "warning",
    });
  }

  if (
    includesAny(normalized, [
      "security",
      "secret",
      "credential",
      "sensitive",
      "internal",
      "customer data",
    ])
  ) {
    signals.push({
      label: "Security posture",
      description: "The draft protects sensitive information and risky actions.",
      tone: "danger",
    });
  }

  if (includesAny(normalized, ["concise", "brief", "short"])) {
    signals.push({
      label: "Concise responses",
      description: "The assistant is instructed to keep answers tight.",
      tone: "success",
    });
  }

  if (
    includesAny(normalized, [
      "clarifying question",
      "clarify",
      "missing",
      "when in doubt",
      "assumption",
    ])
  ) {
    signals.push({
      label: "Decision handling",
      description: "The draft explains what to do when requests are ambiguous.",
      tone: "muted",
    });
  }

  if (signals.length === 0) {
    return [
      {
        label: "Custom behavior",
        description: "No strong pattern detected yet. Add tone, boundaries, and risk handling explicitly.",
        tone: "muted" as const,
      },
    ];
  }

  return signals;
}

function getPromptChecklist(prompt: string, sampleUserPrompt: string) {
  const normalized = prompt.trim().toLowerCase();
  const checklist: string[] = [];

  if (!includesAny(normalized, ["warm", "friendly", "plain language", "tone", "helpful"])) {
    checklist.push("Spell out the tone you want end users to experience.");
  }

  if (!includesAny(normalized, ["refuse", "disallowed", "policy", "rules", "compliance"])) {
    checklist.push("Define what the assistant must refuse, escalate, or verify before answering.");
  }

  if (!includesAny(normalized, ["security", "secret", "credential", "sensitive", "internal"])) {
    checklist.push("Call out how sensitive data, credentials, and internal details should be handled.");
  }

  if (!includesAny(normalized, ["clarify", "clarifying", "assumption", "when in doubt", "missing"])) {
    checklist.push("Explain what the assistant should do when the request is ambiguous or incomplete.");
  }

  if (sampleUserPrompt.trim()) {
    checklist.unshift(`Read the draft against this sample request: "${sampleUserPrompt.trim()}"`);
  }

  return checklist.slice(0, 4);
}

export function SystemPromptSettingsPage() {
  const myRuleSetsQuery = useMyRuleSets();
  const ruleSetId = myRuleSetsQuery.data?.[0]?.id;

  const systemPromptQuery = useSystemPrompt(ruleSetId);
  const updateMutation = useUpdateSystemPrompt(ruleSetId);

  const [draftPrompt, setDraftPrompt] = useState(DEFAULT_SYSTEM_PROMPT);
  const [savedPrompt, setSavedPrompt] = useState(DEFAULT_SYSTEM_PROMPT);
  const [isTestPanelOpen, setIsTestPanelOpen] = useState(false);
  const [testPromptInput, setTestPromptInput] = useState(TEST_PROMPT_PLACEHOLDER);

  useEffect(() => {
    const backendValue = systemPromptQuery.data?.system_prompt;
    const resolved = backendValue ?? DEFAULT_SYSTEM_PROMPT;
    setDraftPrompt(resolved);
    setSavedPrompt(resolved);
  }, [systemPromptQuery.data?.rule_set_id, systemPromptQuery.data?.system_prompt]);

  const isDirty = useMemo(() => draftPrompt !== savedPrompt, [draftPrompt, savedPrompt]);
  const characterCount = draftPrompt.length;
  const behaviorSignals = useMemo(() => getBehaviorSignals(draftPrompt), [draftPrompt]);
  const testingChecklist = useMemo(
    () => getPromptChecklist(draftPrompt, testPromptInput),
    [draftPrompt, testPromptInput]
  );

  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (!isDirty) {
        return;
      }
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);

  const handleSave = async () => {
    if (!ruleSetId) {
      return;
    }

    try {
      const updated = await updateMutation.mutateAsync({
        // Keep user formatting as-is; do not aggressive trim.
        system_prompt: draftPrompt,
      });
      const resolved = updated.system_prompt ?? DEFAULT_SYSTEM_PROMPT;
      setSavedPrompt(resolved);
      setDraftPrompt(resolved);
      toast({
        title: "System prompt updated",
        description: "Prompt settings have been saved.",
        variant: "success",
      });
    } catch (error) {
      toast({
        title: "Save failed",
        description: getErrorMessage(error, "Failed to update system prompt"),
        variant: "destructive",
      });
    }
  };

  const handleReset = () => {
    setDraftPrompt(DEFAULT_SYSTEM_PROMPT);
  };

  const handleApplyTemplate = (templateLabel: string) => {
    const template = behaviorTemplates.find((item) => item.label === templateLabel);
    if (!template) {
      return;
    }

    setDraftPrompt(template.value);
    setTestPromptInput(template.testPrompt);
  };

  if (myRuleSetsQuery.isLoading || systemPromptQuery.isLoading) {
    return (
      <section className="h-full p-6">
        <AppLoadingState
          className="mx-auto max-w-3xl"
          description="Loading the saved assistant instructions for this workspace."
          title="Loading system prompt"
        />
      </section>
    );
  }

  if (myRuleSetsQuery.isError || !ruleSetId) {
    return (
      <section className="h-full p-6">
        <AppAlert title="Unable to resolve current rule set." variant="error" />
      </section>
    );
  }

  if (systemPromptQuery.isError) {
    return (
      <section className="h-full p-6">
        <AppSectionCard title="System prompt unavailable">
          <AppAlert
            description={getErrorMessage(systemPromptQuery.error, "Failed to load system prompt")}
            title="We couldn't load the current system prompt"
            variant="error"
          />
          <AppButton
            onClick={() => {
              void systemPromptQuery.refetch();
            }}
            size="sm"
            type="button"
            variant="secondary"
          >
            Retry
          </AppButton>
        </AppSectionCard>
      </section>
    );
  }

  return (
    <section className="h-full overflow-auto p-6">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
        <AppPageHeader
          actions={
            <AppButton
              leadingIcon={<TestTubeDiagonal className="h-4 w-4" />}
              onClick={() => setIsTestPanelOpen((current) => !current)}
              type="button"
              variant="secondary"
            >
              {isTestPanelOpen ? "Hide prompt check" : "Test prompt"}
            </AppButton>
          }
          meta={`Rule set ID: ${ruleSetId}`}
          subtitle="Set the default instructions that shape how the assistant behaves before it sees any user message."
          title="System Prompt"
        />

        <AppSectionCard
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge
                label={isDirty ? "Unsaved changes" : "Saved"}
                tone={isDirty ? "warning" : "success"}
              />
              <StatusBadge label={`${characterCount} characters`} tone="muted" />
            </div>
          }
          className="border-primary/20 bg-primary/[0.03]"
          description="Use plain language to define tone, boundaries, and what the assistant should do when there is uncertainty or risk."
          title="System Behavior"
        >
          <AppAlert
            description="This prompt becomes the assistant's default operating behavior for the current workspace. Keep it explicit, human-readable, and focused on outcomes."
            title="Make the assistant easy to trust"
            variant="info"
          />

          <div className="space-y-2">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
              Quick templates
            </p>
            <div className="grid gap-3 md:grid-cols-3">
              {behaviorTemplates.map((template) => {
                const isSelected = draftPrompt.trim() === template.value.trim();

                return (
                  <button
                    className={cn(
                      "rounded-2xl border border-border/80 bg-background p-4 text-left transition-colors hover:border-primary/35 hover:bg-primary/[0.03]",
                      isSelected && "border-primary/40 bg-primary/[0.05] ring-2 ring-primary/15"
                    )}
                    key={template.label}
                    onClick={() => handleApplyTemplate(template.label)}
                    type="button"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-foreground">{template.label}</p>
                      <StatusBadge label={template.label} tone={template.tone} />
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">{template.description}</p>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="system-prompt-editor">Assistant instructions</Label>
            <Textarea
              className="min-h-[360px] rounded-2xl border-border/80 bg-background/90 px-4 py-4 font-mono text-sm leading-6 shadow-[inset_0_1px_2px_rgba(15,23,42,0.04)] focus:ring-2 focus:ring-ring/30"
              id="system-prompt-editor"
              onChange={(event) => setDraftPrompt(event.target.value)}
              placeholder={DEFAULT_SYSTEM_PROMPT}
              value={draftPrompt}
            />
            <FieldHelpText>
              Be explicit about tone, boundaries, risk handling, and what the assistant should do when context is missing.
            </FieldHelpText>
          </div>

          <div className="grid gap-3 rounded-2xl border border-border/70 bg-background/70 p-4 md:grid-cols-2">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                <p className="text-sm font-semibold text-foreground">Helper description</p>
              </div>
              <p className="text-sm text-muted-foreground">
                Describe how the assistant should sound, what it should protect, and when it
                should refuse or ask for clarification.
              </p>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Shield className="h-4 w-4 text-warning" />
                <p className="text-sm font-semibold text-foreground">Detected emphasis</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {behaviorSignals.map((signal) => (
                  <StatusBadge key={signal.label} label={signal.label} tone={signal.tone} />
                ))}
              </div>
              <p className="text-sm text-muted-foreground">
                {behaviorSignals[0]?.description}
              </p>
            </div>
          </div>

          <div className={appActionRowClassName}>
            <AppButton
              onClick={handleReset}
              type="button"
              variant="secondary"
            >
              Reset to default
            </AppButton>
            <AppButton
              disabled={!isDirty || updateMutation.isPending}
              onClick={() => {
                void handleSave();
              }}
              type="button"
            >
              {updateMutation.isPending ? "Saving..." : "Save behavior"}
            </AppButton>
          </div>
        </AppSectionCard>

        {isTestPanelOpen ? (
          <AppSectionCard
            description="Use this lightweight check to validate whether your instructions are clear. This panel does not call the backend or run a model."
            title="Prompt Check"
          >
            <div className="space-y-2">
              <Label htmlFor="system-prompt-test-input">Sample user request</Label>
              <Textarea
                className="min-h-[120px] rounded-2xl border-border/80 bg-background/90 px-4 py-4"
                id="system-prompt-test-input"
                onChange={(event) => setTestPromptInput(event.target.value)}
                placeholder={TEST_PROMPT_PLACEHOLDER}
                value={testPromptInput}
              />
              <FieldHelpText>
                Use a realistic request to pressure-test clarity, refusals, and security handling.
              </FieldHelpText>
            </div>

            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                Suggested checks
              </p>
              <div className="space-y-2 rounded-2xl border border-border/70 bg-background p-4">
                {testingChecklist.map((item) => (
                  <div className="flex gap-2" key={item}>
                    <span className="mt-1 h-2 w-2 rounded-full bg-primary" />
                    <p className="text-sm text-foreground">{item}</p>
                  </div>
                ))}
              </div>
            </div>
          </AppSectionCard>
        ) : null}
      </div>
    </section>
  );
}

// Keep legacy name export to avoid touching router and other imports.
export const SystemPromptPage = SystemPromptSettingsPage;
