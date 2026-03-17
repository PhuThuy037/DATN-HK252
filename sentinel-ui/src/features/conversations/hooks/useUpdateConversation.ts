import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateConversation } from "@/features/conversations/api/conversationsApi";
import type { ConversationUpdatePayload } from "@/shared/types";

type UpdateConversationInput = {
  conversationId: string;
  payload: ConversationUpdatePayload;
};

export function useUpdateConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ conversationId, payload }: UpdateConversationInput) =>
      updateConversation(conversationId, payload),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      queryClient.invalidateQueries({
        queryKey: ["conversation", variables.conversationId],
      });
    },
  });
}
