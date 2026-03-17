import { useMutation, useQueryClient } from "@tanstack/react-query";
import { deleteRule } from "@/features/rules/api/rulesApi";
import { ruleQueryKeys } from "@/features/rules/hooks/queryKeys";

export function useDeleteRule(ruleSetId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (ruleId: string) => deleteRule(ruleSetId as string, ruleId),
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
