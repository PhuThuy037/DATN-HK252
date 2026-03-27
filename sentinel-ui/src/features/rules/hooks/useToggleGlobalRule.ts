import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toggleGlobalRule } from "@/features/rules/api/rulesApi";
import { ruleQueryKeys } from "@/features/rules/hooks/queryKeys";
import type { ToggleGlobalRuleRequest } from "@/features/rules/types";

type ToggleGlobalRuleInput = {
  stableKey: string;
  payload: ToggleGlobalRuleRequest;
};

export function useToggleGlobalRule(ruleSetId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ stableKey, payload }: ToggleGlobalRuleInput) =>
      toggleGlobalRule(ruleSetId as string, stableKey, payload),
    onSuccess: () => {
      if (!ruleSetId) {
        return;
      }
      queryClient.invalidateQueries({ queryKey: ruleQueryKeys.rulesRoot(ruleSetId) });
      queryClient.invalidateQueries({
        queryKey: ruleQueryKeys.ruleChangeLogsRoot(ruleSetId),
      });
      queryClient.invalidateQueries({ queryKey: ruleQueryKeys.effectiveRulesRoot });
    },
  });
}
