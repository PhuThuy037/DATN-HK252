import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateSystemPrompt } from "@/features/settings/api/systemPromptApi";
import { settingsQueryKeys } from "@/features/settings/hooks/queryKeys";
import type { UpdateSystemPromptPayload } from "@/features/settings/types";

export function useUpdateSystemPrompt(ruleSetId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: UpdateSystemPromptPayload) =>
      updateSystemPrompt(ruleSetId as string, payload),
    onSuccess: () => {
      if (!ruleSetId) {
        return;
      }
      queryClient.invalidateQueries({
        queryKey: settingsQueryKeys.systemPrompt(ruleSetId),
      });
    },
  });
}
