import { useMutation, useQueryClient } from "@tanstack/react-query";
import { editSuggestion } from "@/features/suggestions/api/suggestionsApi";
import { suggestionQueryKeys } from "@/features/suggestions/hooks/queryKeys";
import type { EditSuggestionRequest } from "@/features/suggestions/types";

export function useEditSuggestion(ruleSetId?: string, suggestionId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: EditSuggestionRequest) =>
      editSuggestion(ruleSetId as string, suggestionId as string, payload),
    onSuccess: (data) => {
      if (!ruleSetId || !suggestionId) {
        return;
      }
      queryClient.invalidateQueries({
        queryKey: suggestionQueryKeys.listBase(ruleSetId),
      });
      queryClient.setQueryData(
        suggestionQueryKeys.detail(ruleSetId, suggestionId),
        (prev: unknown) =>
          prev && typeof prev === "object"
            ? { ...(prev as Record<string, unknown>), ...data }
            : data
      );
      queryClient.invalidateQueries({
        queryKey: suggestionQueryKeys.logsBase(ruleSetId, suggestionId),
      });
    },
  });
}
