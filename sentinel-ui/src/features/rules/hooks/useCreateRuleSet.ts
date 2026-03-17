import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createRuleSet } from "@/features/rules/api/rulesApi";
import { ruleQueryKeys } from "@/features/rules/hooks/queryKeys";
import type { CreateRuleSetRequest } from "@/features/rules/types";

export function useCreateRuleSet() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: CreateRuleSetRequest) => createRuleSet(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ruleQueryKeys.myRuleSets });
    },
  });
}
