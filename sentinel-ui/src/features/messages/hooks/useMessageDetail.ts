import { useQuery } from "@tanstack/react-query";
import { getMessageDetail } from "@/features/messages/api/messagesApi";

export function useMessageDetail(
  conversationId?: string,
  messageId?: string | null
) {
  return useQuery({
    queryKey: ["message-detail", conversationId, messageId],
    queryFn: () => getMessageDetail(conversationId as string, messageId as string),
    enabled: Boolean(conversationId && messageId),
  });
}
