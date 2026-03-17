import { useInfiniteQuery } from "@tanstack/react-query";
import { getMessages } from "@/features/messages/api/messagesApi";

const PAGE_LIMIT = 20;

export function useInfiniteMessages(conversationId?: string) {
  return useInfiniteQuery({
    queryKey: ["messages-infinite", conversationId],
    initialPageParam: undefined as number | undefined,
    queryFn: ({ pageParam }) =>
      getMessages(conversationId as string, {
        before_seq: pageParam,
        limit: PAGE_LIMIT,
      }),
    getNextPageParam: (lastPage) =>
      lastPage?.page?.has_more
        ? (lastPage.page.next_before_seq ?? undefined)
        : undefined,
    enabled: Boolean(conversationId),
  });
}
