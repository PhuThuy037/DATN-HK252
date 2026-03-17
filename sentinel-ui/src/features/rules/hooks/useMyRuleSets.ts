import { useQuery } from "@tanstack/react-query";
import { getMyRuleSets } from "@/features/rules/api/rulesApi";
import { ruleQueryKeys } from "@/features/rules/hooks/queryKeys";

type UseMyRuleSetsOptions = {
  enabled?: boolean;
};

export function useMyRuleSets(options?: UseMyRuleSetsOptions) {
  return useQuery({
    queryKey: ruleQueryKeys.myRuleSets,
    queryFn: getMyRuleSets,
    enabled: options?.enabled ?? true,
  });
}
