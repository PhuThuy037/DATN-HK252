import { useMutation, useQueryClient } from "@tanstack/react-query";
import { deleteConversation } from "@/features/conversations/api/conversationsApi";

export function useDeleteConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (conversationId: string) => deleteConversation(conversationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
}
