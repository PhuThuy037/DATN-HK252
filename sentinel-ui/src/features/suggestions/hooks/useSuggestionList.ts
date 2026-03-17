import { useQuery } from "@tanstack/react-query";
import { getSuggestionList } from "@/features/suggestions/api/suggestionsApi";
import { suggestionQueryKeys } from "@/features/suggestions/hooks/queryKeys";
import type { SuggestionStatus } from "@/features/suggestions/types";

export function useSuggestionList(
  ruleSetId?: string,
  status?: SuggestionStatus,
  limit?: number
) {
  return useQuery({
    queryKey: ruleSetId
      ? suggestionQueryKeys.list(ruleSetId, status, limit)
      : ["suggestions", "list", "unknown"],
    queryFn: () => getSuggestionList(ruleSetId as string, { status, limit }),
    enabled: Boolean(ruleSetId),
  });
}
