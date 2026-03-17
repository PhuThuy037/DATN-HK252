import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateRule } from "@/features/rules/api/rulesApi";
import { ruleQueryKeys } from "@/features/rules/hooks/queryKeys";
import type { UpdateRuleRequest } from "@/features/rules/types";

type UpdateRuleInput = {
  ruleId: string;
  payload: UpdateRuleRequest;
};

export function useUpdateRule(ruleSetId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ ruleId, payload }: UpdateRuleInput) =>
      updateRule(ruleSetId as string, ruleId, payload),
    onSuccess: () => {
      if (!ruleSetId) {
        return;
      }
      queryClient.invalidateQueries({ queryKey: ruleQueryKeys.rules(ruleSetId) });
      queryClient.invalidateQueries({
        queryKey: ruleQueryKeys.ruleChangeLogs(ruleSetId),
      });
      queryClient.invalidateQueries({ queryKey: ruleQueryKeys.effectiveRules });
    },
  });
}
