import { useMutation } from "@tanstack/react-query";
import { simulateSuggestion } from "@/features/suggestions/api/suggestionsApi";
import type { SimulateSuggestionRequest } from "@/features/suggestions/types";

export function useSimulateSuggestion(ruleSetId?: string, suggestionId?: string) {
  return useMutation({
    mutationFn: (payload: SimulateSuggestionRequest) =>
      simulateSuggestion(ruleSetId as string, suggestionId as string, payload),
  });
}
