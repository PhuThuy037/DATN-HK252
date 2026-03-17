import { cn } from "@/shared/lib/utils";
import type { SuggestionStatus } from "@/features/suggestions/types";

export type SuggestionStepKey =
  | "generate"
  | "draft"
  | "simulate"
  | "review"
  | "decision"
  | "apply";

const steps: Array<{ key: SuggestionStepKey; label: string }> = [
  { key: "generate", label: "Generate" },
  { key: "draft", label: "Draft" },
  { key: "simulate", label: "Simulate" },
  { key: "review", label: "Review" },
  { key: "decision", label: "Confirm / Reject" },
  { key: "apply", label: "Apply" },
];

function stepIndexByStatus(status: SuggestionStatus) {
  if (status === "draft") {
    return 1;
  }
  if (status === "approved") {
    return 4;
  }
  if (status === "applied") {
    return 5;
  }
  return 4;
}

type SuggestionStepperProps = {
  status: SuggestionStatus;
  activeStep: SuggestionStepKey;
  onStepChange: (step: SuggestionStepKey) => void;
};

export function SuggestionStepper({ status, activeStep, onStepChange }: SuggestionStepperProps) {
  const statusIndex = stepIndexByStatus(status);

  return (
    <div className="rounded-lg border p-3">
      <p className="text-xs text-muted-foreground">
        Guided workflow only. You can revisit Draft/Simulate/Review before final apply.
      </p>
      <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-6">
        {steps.map((step, index) => {
          const isActive = activeStep === step.key;
          const isReached = index <= statusIndex;

          return (
            <button
              className={cn(
                "rounded-md border px-2 py-1.5 text-left text-xs transition-colors",
                isActive && "border-primary bg-primary/10 text-primary",
                !isActive && isReached && "border-emerald-200 bg-emerald-50 text-emerald-700",
                !isActive && !isReached && "border-border bg-background text-muted-foreground hover:bg-muted/30"
              )}
              key={step.key}
              onClick={() => onStepChange(step.key)}
              type="button"
            >
              {step.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
