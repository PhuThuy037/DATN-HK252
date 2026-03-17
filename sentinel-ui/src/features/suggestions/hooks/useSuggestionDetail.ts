import { useQuery } from "@tanstack/react-query";
import { getSuggestionDetail } from "@/features/suggestions/api/suggestionsApi";
import { suggestionQueryKeys } from "@/features/suggestions/hooks/queryKeys";

export function useSuggestionDetail(ruleSetId?: string, suggestionId?: string) {
  return useQuery({
    queryKey:
      ruleSetId && suggestionId
        ? suggestionQueryKeys.detail(ruleSetId, suggestionId)
        : ["suggestions", "detail", "unknown"],
    queryFn: () => getSuggestionDetail(ruleSetId as string, suggestionId as string),
    enabled: Boolean(ruleSetId && suggestionId),
  });
}
