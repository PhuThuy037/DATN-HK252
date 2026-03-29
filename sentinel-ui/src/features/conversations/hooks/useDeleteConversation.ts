import { useMutation, useQueryClient } from "@tanstack/react-query";
import { deleteConversation } from "@/features/conversations/api/conversationsApi";
import type { ConversationsPage } from "@/shared/types";

export function useDeleteConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (conversationId: string) => deleteConversation(conversationId),
    onSuccess: (_data, conversationId) => {
      queryClient.setQueriesData(
        { queryKey: ["conversations"] },
        (current: unknown) => {
          const typed = current as ConversationsPage | undefined;
          if (!typed || !Array.isArray(typed.items)) {
            return typed;
          }
          const nextItems = typed.items.filter(
            (item) => String(item.id) !== String(conversationId)
          );
          if (nextItems.length === typed.items.length) {
            return typed;
          }
          return { ...typed, items: nextItems };
        }
      );
      queryClient.removeQueries({
        queryKey: ["conversation", conversationId],
        exact: true,
      });
      queryClient.removeQueries({
        queryKey: ["messages", conversationId],
        exact: true,
      });
      queryClient.removeQueries({
        queryKey: ["messages-infinite", conversationId],
        exact: true,
      });
      queryClient.removeQueries({
        queryKey: ["message-detail", conversationId],
      });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
}
