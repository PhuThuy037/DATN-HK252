import { useInfiniteQuery } from "@tanstack/react-query";
import { getEffectiveRules } from "@/features/rules/api/rulesApi";
import { ruleQueryKeys } from "@/features/rules/hooks/queryKeys";

type UseEffectiveRulesOptions = {
  limit?: number;
  enabled?: boolean;
};

const DEFAULT_EFFECTIVE_RULES_PAGE_LIMIT = 20;

export function useEffectiveRules(options?: UseEffectiveRulesOptions) {
  const limit = options?.limit ?? DEFAULT_EFFECTIVE_RULES_PAGE_LIMIT;

  return useInfiniteQuery({
    queryKey: ruleQueryKeys.effectiveRules(limit),
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) =>
      getEffectiveRules({
        limit,
        cursor: pageParam,
      }),
    getNextPageParam: (lastPage) =>
      lastPage.hasMore ? (lastPage.nextCursor ?? undefined) : undefined,
    enabled: options?.enabled ?? true,
  });
}
