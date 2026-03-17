import { useQuery } from "@tanstack/react-query";
import { getRuleChangeLogs } from "@/features/rules/api/rulesApi";
import { ruleQueryKeys } from "@/features/rules/hooks/queryKeys";

type UseRuleChangeLogsOptions = {
  limit?: number;
};

export function useRuleChangeLogs(
  ruleSetId?: string,
  options?: UseRuleChangeLogsOptions
) {
  return useQuery({
    queryKey: ruleSetId
      ? [...ruleQueryKeys.ruleChangeLogs(ruleSetId), options?.limit ?? null]
      : ["rule-change-logs", "unknown"],
    queryFn: () =>
      getRuleChangeLogs(ruleSetId as string, {
        limit: options?.limit,
      }),
    enabled: Boolean(ruleSetId),
  });
}
