import { useQuery } from "@tanstack/react-query";
import { getSystemPrompt } from "@/features/settings/api/systemPromptApi";
import { settingsQueryKeys } from "@/features/settings/hooks/queryKeys";

export function useSystemPrompt(ruleSetId?: string) {
  return useQuery({
    queryKey: ruleSetId
      ? settingsQueryKeys.systemPrompt(ruleSetId)
      : ["system-prompt", "unknown"],
    queryFn: () => getSystemPrompt(ruleSetId as string),
    enabled: Boolean(ruleSetId),
  });
}
