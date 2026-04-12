import { useQuery } from "@tanstack/react-query";
import { getRuleDetail } from "@/features/rules/api/rulesApi";
import { ruleQueryKeys } from "@/features/rules/hooks/queryKeys";

export function useRuleDetail(ruleId?: string) {
  return useQuery({
    queryKey: ruleId ? ruleQueryKeys.ruleDetail(ruleId) : ["rule-detail", "unknown"],
    queryFn: () => getRuleDetail(ruleId as string),
    enabled: Boolean(ruleId),
  });
}
