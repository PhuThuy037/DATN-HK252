import { useQuery } from "@tanstack/react-query";
import { getMessages } from "@/features/messages/api/messagesApi";

export function useMessages(conversationId?: string) {
  return useQuery({
    queryKey: ["messages", conversationId],
    queryFn: () => getMessages(conversationId as string),
    enabled: Boolean(conversationId),
  });
}
