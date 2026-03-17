import { useQuery } from "@tanstack/react-query";
import { getConversations } from "@/features/conversations/api/conversationsApi";

type UseConversationsParams = {
  limit?: number;
  status?: "active" | "archived";
};

export function useConversations(params?: UseConversationsParams) {
  return useQuery({
    queryKey: ["conversations", params],
    queryFn: () => getConversations(params),
  });
}
