import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateRule } from "@/features/rules/api/rulesApi";
import { ruleQueryKeys } from "@/features/rules/hooks/queryKeys";
import type {
  UpdateRuleRequest,
  UpdateRuleWithContextRequest,
} from "@/features/rules/types";

type UpdateRuleInput = {
  ruleId: string;
  payload: UpdateRuleRequest | UpdateRuleWithContextRequest;
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
      queryClient.invalidateQueries({ queryKey: ruleQueryKeys.rulesRoot(ruleSetId) });
      queryClient.invalidateQueries({
        predicate: (query) =>
          Array.isArray(query.queryKey) && query.queryKey[0] === "rule-detail",
      });
      queryClient.invalidateQueries({
        queryKey: ruleQueryKeys.ruleChangeLogsRoot(ruleSetId),
      });
      queryClient.invalidateQueries({ queryKey: ruleQueryKeys.effectiveRulesRoot });
    },
  });
}
