import { Check, Lock } from "lucide-react";
import { cn } from "@/shared/lib/utils";

export type SuggestionStepKey =
  | "generate"
  | "draft"
  | "simulate"
  | "review"
  | "decision"
  | "apply";

export const suggestionWorkflowSteps: Array<{ key: SuggestionStepKey; label: string; shortLabel: string }> = [
  { key: "generate", label: "Generate", shortLabel: "1 Generate" },
  { key: "draft", label: "Draft", shortLabel: "2 Draft" },
  { key: "simulate", label: "Simulate", shortLabel: "3 Simulate" },
  { key: "review", label: "Review", shortLabel: "4 Review" },
  { key: "decision", label: "Confirm", shortLabel: "5 Confirm" },
  { key: "apply", label: "Apply", shortLabel: "6 Apply" },
];

export type SuggestionStepState = "current" | "done" | "available" | "locked";

const steps = suggestionWorkflowSteps;

type SuggestionStepperProps = {
  activeStep: SuggestionStepKey;
  stepStates: Record<SuggestionStepKey, SuggestionStepState>;
  onStepChange: (step: SuggestionStepKey) => void;
};

export function SuggestionStepper({
  activeStep,
  stepStates,
  onStepChange,
}: SuggestionStepperProps) {
  return (
    <div className="rounded-2xl border border-border/80 bg-background p-4 shadow-app-sm">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
        Guided workflow
      </p>
      <p className="mt-1 text-sm text-muted-foreground">
        Follow each step in order. Completed steps show a check mark, and locked steps unlock as you move forward.
      </p>

      <div className="mt-4 grid gap-2 md:grid-cols-6">
        {steps.map((step, index) => {
          const isActive = activeStep === step.key;
          const state = stepStates[step.key];
          const isLocked = state === "locked";
          const isDone = state === "done";

          return (
            <button
              aria-current={isActive ? "step" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-xl border px-3 py-3 text-left transition-colors",
                isActive && "border-primary bg-primary/10 text-primary shadow-app-sm",
                isDone && "border-success-border bg-success-muted text-success",
                state === "available" && "border-border/80 bg-background text-foreground hover:bg-muted/30",
                isLocked && "cursor-not-allowed border-border/60 bg-muted/20 text-muted-foreground"
              )}
              disabled={isLocked}
              key={step.key}
              onClick={() => onStepChange(step.key)}
              type="button"
            >
              <span
                className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-xs font-semibold",
                  isActive && "border-primary bg-primary text-primary-foreground",
                  isDone && "border-success-border bg-success text-success-foreground",
                  state === "available" && "border-border/80 bg-muted text-foreground",
                  isLocked && "border-border bg-background text-muted-foreground"
                )}
              >
                {isDone ? <Check className="h-4 w-4" /> : isLocked ? <Lock className="h-3.5 w-3.5" /> : index + 1}
              </span>

              <span className="min-w-0">
                <span className="block text-[11px] font-medium uppercase tracking-[0.14em] opacity-75">
                  Step {index + 1}
                </span>
                <span className="mt-0.5 block text-sm font-semibold">{step.label}</span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
