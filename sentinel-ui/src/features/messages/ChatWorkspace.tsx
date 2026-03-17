import { MessageComposer } from "@/features/messages/components/MessageComposer";
import { MessageList } from "@/features/messages/components/MessageList";
import { useMessages } from "@/features/messages/hooks/useMessages";
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

  const messagesQuery = useMessages(conversationId);
  const sendMutation = useSendMessage();

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
    <section className="flex h-full flex-col">
      <div className="min-h-0 flex-1 p-4">
        <Card className="h-full overflow-hidden">
          <MessageList
            isError={messagesQuery.isError}
            isLoading={messagesQuery.isLoading}
            messages={messagesQuery.data?.items ?? []}
            onSelectMessage={setSelectedMessageId}
            selectedMessageId={selectedMessageId}
          />
        </Card>
      </div>

      <footer className="border-t px-4 py-4">
        <MessageComposer
          disabled={!conversationId}
          isSending={sendMutation.isPending}
          onSend={handleSend}
        />
      </footer>
    </section>
  );
}
