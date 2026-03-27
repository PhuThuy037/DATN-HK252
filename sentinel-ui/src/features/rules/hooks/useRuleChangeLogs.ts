import { useInfiniteQuery } from "@tanstack/react-query";
import { getRuleChangeLogs } from "@/features/rules/api/rulesApi";
import { ruleQueryKeys } from "@/features/rules/hooks/queryKeys";

type UseRuleChangeLogsOptions = {
  limit?: number;
  enabled?: boolean;
};

export function useRuleChangeLogs(
  ruleSetId?: string,
  options?: UseRuleChangeLogsOptions
) {
  const limit = options?.limit ?? 20;

  return useInfiniteQuery({
    queryKey: ruleSetId
      ? ruleQueryKeys.ruleChangeLogs(ruleSetId, limit)
      : ["rule-change-logs", "unknown", limit],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) =>
      getRuleChangeLogs(ruleSetId as string, {
        limit,
        cursor: pageParam,
      }),
    getNextPageParam: (lastPage) =>
      lastPage.hasMore ? (lastPage.nextCursor ?? undefined) : undefined,
    enabled: Boolean(ruleSetId) && (options?.enabled ?? true),
  });
}
