import { useMutation, useQueryClient } from "@tanstack/react-query";
import { sendMessage } from "@/features/messages/api/messagesApi";
import type { SendMessageRequest } from "@/shared/types";

type SendMessageInput = {
  conversationId: string;
  payload: SendMessageRequest;
};

export function useSendMessage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ conversationId, payload }: SendMessageInput) =>
      sendMessage(conversationId, payload),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["messages", variables.conversationId],
      });
      queryClient.invalidateQueries({
        queryKey: ["messages-infinite", variables.conversationId],
      });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      queryClient.invalidateQueries({
        queryKey: ["message-detail", variables.conversationId],
      });
    },
  });
}
