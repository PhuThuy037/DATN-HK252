import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createRule } from "@/features/rules/api/rulesApi";
import { ruleQueryKeys } from "@/features/rules/hooks/queryKeys";
import type { CreateRuleRequest } from "@/features/rules/types";

export function useCreateRule(ruleSetId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: CreateRuleRequest) =>
      createRule(ruleSetId as string, payload),
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
