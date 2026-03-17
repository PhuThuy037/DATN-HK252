import { useQuery } from "@tanstack/react-query";
import { getEffectiveRules } from "@/features/rules/api/rulesApi";
import { ruleQueryKeys } from "@/features/rules/hooks/queryKeys";

export function useEffectiveRules() {
  return useQuery({
    queryKey: ruleQueryKeys.effectiveRules,
    queryFn: getEffectiveRules,
  });
}
