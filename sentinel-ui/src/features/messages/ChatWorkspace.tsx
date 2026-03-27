import { useCallback, useMemo } from "react";
import { MessageComposer } from "@/features/messages/components/MessageComposer";
import { MessageList } from "@/features/messages/components/MessageList";
import { useInfiniteMessages } from "@/features/messages/hooks/useInfiniteMessages";
import { useSendMessage } from "@/features/messages/hooks/useSendMessage";
import { useChatUiStore } from "@/features/messages/store/chatUiStore";
import { Card } from "@/shared/ui/card";
import { toast } from "@/shared/ui/use-toast";

type ChatWorkspaceProps = {
  conversationId?: string;
};

export function ChatWorkspace({ conversationId }: ChatWorkspaceProps) {
  const selectedMessageId = useChatUiStore((state) => state.selectedMessageId);
  const setSelectedMessageId = useChatUiStore((state) => state.setSelectedMessageId);

  const messagesQuery = useInfiniteMessages(conversationId);
  const sendMutation = useSendMessage();
  const messages = useMemo(
    () =>
      (messagesQuery.data?.pages ?? [])
        .slice()
        .reverse()
        .flatMap((page) => page.items),
    [messagesQuery.data?.pages]
  );

  const handleLoadOlderMessages = useCallback(async () => {
    if (!messagesQuery.hasNextPage || messagesQuery.isFetchingNextPage) {
      return;
    }
    await messagesQuery.fetchNextPage();
  }, [
    messagesQuery.fetchNextPage,
    messagesQuery.hasNextPage,
    messagesQuery.isFetchingNextPage,
  ]);

  const handleSend = async (content: string) => {
    if (!conversationId) {
      return;
    }

    try {
      const sent = await sendMutation.mutateAsync({
        conversationId,
        payload: { content },
      });

      if (sent.id) {
        setSelectedMessageId(sent.id);
      }
    } catch (error) {
      toast({
        title: "Send failed",
        description: error instanceof Error ? error.message : "Failed to send message.",
        variant: "destructive",
      });
      throw error;
    }
  };

  return (
    <section className="flex h-full flex-col bg-[linear-gradient(180deg,rgba(248,250,252,0.96),rgba(255,255,255,1))]">
      <div className="min-h-0 flex-1 px-4 py-4">
        <Card className="h-full overflow-hidden rounded-[28px] border-border/80 bg-background/80 shadow-app-md">
          <MessageList
            isError={messagesQuery.isError}
            isLoading={messagesQuery.isLoading}
            isFetchingMore={messagesQuery.isFetchingNextPage}
            messages={messages}
            hasMore={Boolean(messagesQuery.hasNextPage)}
            onLoadMore={handleLoadOlderMessages}
            onSelectMessage={setSelectedMessageId}
            selectedMessageId={selectedMessageId}
          />
        </Card>
      </div>

      <footer className="border-t border-border/70 bg-background/80 px-4 py-4 backdrop-blur">
        <MessageComposer
          disabled={!conversationId}
          isSending={sendMutation.isPending}
          onSend={handleSend}
        />
      </footer>
    </section>
  );
}
