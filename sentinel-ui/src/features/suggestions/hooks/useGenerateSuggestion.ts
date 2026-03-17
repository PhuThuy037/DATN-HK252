import { useMutation, useQueryClient } from "@tanstack/react-query";
import { generateSuggestion } from "@/features/suggestions/api/suggestionsApi";
import { suggestionQueryKeys } from "@/features/suggestions/hooks/queryKeys";
import type { GenerateSuggestionRequest } from "@/features/suggestions/types";

export function useGenerateSuggestion(ruleSetId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: GenerateSuggestionRequest) =>
      generateSuggestion(ruleSetId as string, payload),
    onSuccess: (data) => {
      if (!ruleSetId) {
        return;
      }
      queryClient.invalidateQueries({
        queryKey: suggestionQueryKeys.listBase(ruleSetId),
      });
      queryClient.setQueryData(suggestionQueryKeys.detail(ruleSetId, data.id), data);
    },
  });
}
