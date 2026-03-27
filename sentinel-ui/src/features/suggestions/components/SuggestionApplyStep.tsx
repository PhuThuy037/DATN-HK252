import { useNavigate } from "react-router-dom";
import type { RuleSuggestionGetOut } from "@/features/suggestions/types";
import { canApply } from "@/features/suggestions/components/StatusBadge";
import { SuggestionApplyResultCard } from "@/features/suggestions/components/SuggestionApplyResultCard";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppButton } from "@/shared/ui/app-button";
import { EmptyState } from "@/shared/ui/empty-state";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { StatusBadge } from "@/shared/ui/status-badge";

type SuggestionApplyStepProps = {
  suggestion: RuleSuggestionGetOut;
  isApplying: boolean;
  onOpenApply: () => void;
};

export function SuggestionApplyStep({
  suggestion,
  isApplying,
  onOpenApply,
}: SuggestionApplyStepProps) {
  const navigate = useNavigate();
  const appliedRuleId =
    typeof suggestion.applied_result_json?.rule_id === "string"
      ? suggestion.applied_result_json.rule_id
      : "";

  return (
    <AppSectionCard
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge label="Step 6 of 6" tone="muted" />
          {suggestion.status === "applied" ? <StatusBadge label="Done" tone="success" /> : null}
        </div>
      }
      description="Apply this approved suggestion to create or update runtime rule data."
      title="Apply"
    >

      {suggestion.status === "applied" ? (
        <>
          <AppAlert
            description="The suggestion has been applied successfully and is ready for follow-up validation."
            title="Rule applied successfully"
            variant="success"
          />

          {suggestion.applied_result_json ? (
            <SuggestionApplyResultCard appliedResultJson={suggestion.applied_result_json} />
          ) : (
            <EmptyState
              description="The rule was applied, but no additional result payload was returned."
              title="No apply result details"
            />
          )}

          <div className="flex flex-wrap gap-2">
            <AppButton
              onClick={() =>
                navigate("/app/settings/rules", {
                  state: appliedRuleId ? { highlightRuleId: appliedRuleId } : undefined,
                })
              }
              type="button"
              variant="secondary"
            >
              Go to rules
            </AppButton>
            <AppButton onClick={() => navigate("/app/chat")} type="button">
              Test in chat
            </AppButton>
          </div>
        </>
      ) : (
        <>
          <div>
            <AppButton
              disabled={!canApply(suggestion.status) || isApplying}
              onClick={onOpenApply}
              type="button"
            >
              {isApplying ? "Applying..." : "Apply suggestion"}
            </AppButton>
          </div>
        </>
      )}
    </AppSectionCard>
  );
}
