import { useInfiniteQuery } from "@tanstack/react-query";
import { getRuleSetRules } from "@/features/rules/api/rulesApi";
import { ruleQueryKeys } from "@/features/rules/hooks/queryKeys";
import type { RuleListTab } from "@/features/rules/types";

type UseRulesOptions = {
  tab?: RuleListTab;
  limit?: number;
  enabled?: boolean;
};

const DEFAULT_RULES_PAGE_LIMIT = 20;

export function useRules(ruleSetId?: string, options?: UseRulesOptions) {
  const tab = options?.tab ?? "all";
  const limit = options?.limit ?? DEFAULT_RULES_PAGE_LIMIT;

  return useInfiniteQuery({
    queryKey: ruleSetId
      ? ruleQueryKeys.rules(ruleSetId, tab, limit)
      : ["rules", "unknown", tab, limit],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) =>
      getRuleSetRules(ruleSetId as string, {
        tab,
        limit,
        cursor: pageParam,
      }),
    getNextPageParam: (lastPage) =>
      lastPage.hasMore ? (lastPage.nextCursor ?? undefined) : undefined,
    enabled: Boolean(ruleSetId) && (options?.enabled ?? true),
  });
}
