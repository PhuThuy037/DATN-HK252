import { useMutation, useQueryClient } from "@tanstack/react-query";
import { applySuggestion } from "@/features/suggestions/api/suggestionsApi";
import { suggestionQueryKeys } from "@/features/suggestions/hooks/queryKeys";
import type { ApplySuggestionRequest } from "@/features/suggestions/types";

export function useApplySuggestion(ruleSetId?: string, suggestionId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: ApplySuggestionRequest) =>
      applySuggestion(ruleSetId as string, suggestionId as string, payload),
    onSuccess: () => {
      if (!ruleSetId || !suggestionId) {
        return;
      }
      queryClient.invalidateQueries({
        queryKey: suggestionQueryKeys.listBase(ruleSetId),
      });
      queryClient.invalidateQueries({
        queryKey: suggestionQueryKeys.detail(ruleSetId, suggestionId),
      });
      queryClient.invalidateQueries({
        queryKey: suggestionQueryKeys.logsBase(ruleSetId, suggestionId),
      });
    },
  });
}
