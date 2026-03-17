import { useQuery } from "@tanstack/react-query";
import { getConversation } from "@/features/conversations/api/conversationsApi";

export function useConversation(conversationId?: string) {
  return useQuery({
    queryKey: ["conversation", conversationId],
    queryFn: () => getConversation(conversationId as string),
    enabled: Boolean(conversationId),
  });
}
