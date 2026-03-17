import { useQuery } from "@tanstack/react-query";
import { getSuggestionLogs } from "@/features/suggestions/api/suggestionsApi";
import { suggestionQueryKeys } from "@/features/suggestions/hooks/queryKeys";

export function useSuggestionLogs(
  ruleSetId?: string,
  suggestionId?: string,
  limit = 50
) {
  return useQuery({
    queryKey:
      ruleSetId && suggestionId
        ? suggestionQueryKeys.logs(ruleSetId, suggestionId, limit)
        : ["suggestions", "logs", "unknown"],
    queryFn: () =>
      getSuggestionLogs(ruleSetId as string, suggestionId as string, { limit }),
    enabled: Boolean(ruleSetId && suggestionId),
  });
}
