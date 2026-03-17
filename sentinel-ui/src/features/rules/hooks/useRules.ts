import { useQuery } from "@tanstack/react-query";
import { getRuleSetRules } from "@/features/rules/api/rulesApi";
import { ruleQueryKeys } from "@/features/rules/hooks/queryKeys";

export function useRules(ruleSetId?: string) {
  return useQuery({
    queryKey: ruleSetId ? ruleQueryKeys.rules(ruleSetId) : ["rules", "unknown"],
    queryFn: () => getRuleSetRules(ruleSetId as string),
    enabled: Boolean(ruleSetId),
  });
}
