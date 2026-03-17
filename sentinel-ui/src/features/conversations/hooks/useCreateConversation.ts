import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createPersonalConversation,
} from "@/features/conversations/api/conversationsApi";
import type { CreateConversationPayload } from "@/shared/types";

export function useCreateConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload?: CreateConversationPayload) =>
      createPersonalConversation(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
}
