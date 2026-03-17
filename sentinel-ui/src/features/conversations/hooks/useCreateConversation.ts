import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createPersonalConversation,
  createRuleSetConversation,
} from "@/features/conversations/api/conversationsApi";
import { useRuleSetStore } from "@/features/rules/store/ruleSetStore";
import type { CreateConversationPayload } from "@/shared/types";

export function useCreateConversation() {
  const queryClient = useQueryClient();
  const currentRuleSetId = useRuleSetStore((state) => state.currentRuleSetId);

  return useMutation({
    mutationFn: async (payload?: CreateConversationPayload) => {
      if (currentRuleSetId) {
        return createRuleSetConversation(currentRuleSetId, payload);
      }

      // Backward compatibility fallback for accounts without an active rule set.
      return createPersonalConversation(payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
}
