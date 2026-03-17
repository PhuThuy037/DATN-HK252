import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useConversations } from "@/features/conversations/hooks/useConversations";
import { useConversation } from "@/features/conversations/hooks/useConversation";
import { EmptyChatState } from "@/features/messages/components/EmptyChatState";
import { MessageComposer } from "@/features/messages/components/MessageComposer";
import { MessageList } from "@/features/messages/components/MessageList";
import { useMessages } from "@/features/messages/hooks/useMessages";
import { useSendMessage } from "@/features/messages/hooks/useSendMessage";
import { useChatUiStore } from "@/features/messages/store/chatUiStore";
import { Card } from "@/shared/ui/card";
import { toast } from "@/shared/ui/use-toast";
import type { MessageListItem } from "@/shared/types";

type FailedMessageItem = {
  id: string;
  content: string;
  created_at: string;
  retrying: boolean;
};

export function ChatPage() {
  const navigate = useNavigate();
  const { conversationId } = useParams();

  const setSelectedMessageId = useChatUiStore((state) => state.setSelectedMessageId);
  const selectedMessageId = useChatUiStore((state) => state.selectedMessageId);
  const clearSelectedMessageId = useChatUiStore(
    (state) => state.clearSelectedMessageId
  );
  const [failedMessages, setFailedMessages] = useState<FailedMessageItem[]>([]);

  const conversationsQuery = useConversations();
  const conversationQuery = useConversation(conversationId);
  const messagesQuery = useMessages(conversationId);
  const sendMessageMutation = useSendMessage();

  const conversations = useMemo(
    () => conversationsQuery.data?.items ?? [],
    [conversationsQuery.data?.items]
  );
  const messages = useMemo(
    () => messagesQuery.data?.items ?? [],
    [messagesQuery.data?.items]
  );

  useEffect(() => {
    clearSelectedMessageId();
    setFailedMessages([]);
  }, [conversationId, clearSelectedMessageId]);

  const failedMessageIds = useMemo(
    () => failedMessages.map((item) => item.id),
    [failedMessages]
  );

  const retryingMessageIds = useMemo(
    () => failedMessages.filter((item) => item.retrying).map((item) => item.id),
    [failedMessages]
  );

  const mergedMessages = useMemo(() => {
    const pendingAsMessages: MessageListItem[] = failedMessages.map((item) => ({
      id: item.id,
      role: "user",
      content: item.content,
      created_at: item.created_at,
      state: "failed",
    }));
    return [...messages, ...pendingAsMessages];
  }, [failedMessages, messages]);

  useEffect(() => {
    if (conversationId || conversationsQuery.isLoading) {
      return;
    }

    if (conversations.length > 0) {
      navigate(`/app/chat/${conversations[0].id}`, { replace: true });
    }
  }, [conversationId, conversations, conversationsQuery.isLoading, navigate]);

  const handleSendMessage = useCallback(
    async (content: string) => {
      if (!conversationId) {
        return;
      }

      try {
        const sent = await sendMessageMutation.mutateAsync({
          conversationId,
          payload: { content, input_type: "user_input" },
        });

        if (sent.id) {
          setSelectedMessageId(sent.id);
        }
      } catch (error) {
        const failedId = `failed-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        setFailedMessages((prev) => [
          ...prev,
          {
            id: failedId,
            content,
            created_at: new Date().toISOString(),
            retrying: false,
          },
        ]);

        toast({
          title: "Send failed",
          description: error instanceof Error ? error.message : "Failed to send message.",
          variant: "destructive",
        });
        throw error;
      }
    },
    [conversationId, sendMessageMutation, setSelectedMessageId]
  );

  const handleRetryFailedMessage = useCallback(
    async (messageId: string) => {
      if (!conversationId) {
        return;
      }

      const target = failedMessages.find((item) => item.id === messageId);
      if (!target || target.retrying) {
        return;
      }

      setFailedMessages((prev) =>
        prev.map((item) =>
          item.id === messageId ? { ...item, retrying: true } : item
        )
      );

      try {
        const sent = await sendMessageMutation.mutateAsync({
          conversationId,
          payload: { content: target.content, input_type: "user_input" },
        });

        setFailedMessages((prev) => prev.filter((item) => item.id !== messageId));
        if (sent.id) {
          setSelectedMessageId(sent.id);
        }
      } catch (error) {
        setFailedMessages((prev) =>
          prev.map((item) =>
            item.id === messageId ? { ...item, retrying: false } : item
          )
        );

        toast({
          title: "Retry failed",
          description: error instanceof Error ? error.message : "Retry failed.",
          variant: "destructive",
        });
      }
    },
    [conversationId, failedMessages, sendMessageMutation, setSelectedMessageId]
  );

  const handleSelectMessage = useCallback(
    (messageId: string) => {
      if (failedMessageIds.includes(messageId)) {
        return;
      }
      setSelectedMessageId(messageId);
    },
    [failedMessageIds, setSelectedMessageId]
  );

  if (!conversationId) {
    return (
      <section className="flex h-full items-center justify-center p-6">
        <div className="w-full max-w-xl">
          {conversationsQuery.isLoading && (
            <p className="text-sm text-muted-foreground">Loading conversations...</p>
          )}

          {conversationsQuery.isError && (
            <p className="text-sm text-destructive">Failed to load conversations.</p>
          )}

          {!conversationsQuery.isLoading &&
            !conversationsQuery.isError &&
            conversations.length === 0 && (
              <EmptyChatState
                description="Create your first conversation from the sidebar to start chatting."
                title="No conversations yet"
              />
            )}
        </div>
      </section>
    );
  }

  if (conversationQuery.isError) {
    return (
      <section className="flex h-full items-center justify-center p-6">
        <div className="w-full max-w-xl">
          <Card className="p-6">
            <h2 className="text-base font-semibold">Conversation not found</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              This conversation does not exist or you do not have access.
            </p>
          </Card>
        </div>
      </section>
    );
  }

  return (
    <section className="flex h-full min-h-0 flex-col bg-background">
      <header className="shrink-0 border-b px-6 py-4">
        <h2 className="text-base font-semibold">
          {conversationQuery.isLoading
            ? "Loading conversation..."
            : conversationQuery.data?.title?.trim() || "Untitled conversation"}
        </h2>
        <p className="text-xs text-muted-foreground">
          Conversation ID: {conversationId}
        </p>
      </header>

      <div className="min-h-0 flex-1 p-4">
        <Card className="h-full overflow-hidden rounded-2xl">
          <MessageList
            failedMessageIds={failedMessageIds}
            isError={messagesQuery.isError}
            isLoading={messagesQuery.isLoading}
            isSending={sendMessageMutation.isPending}
            messages={mergedMessages}
            onRetryMessage={handleRetryFailedMessage}
            onSelectMessage={handleSelectMessage}
            retryingMessageIds={retryingMessageIds}
            selectedMessageId={selectedMessageId}
          />
        </Card>
      </div>

      <footer className="shrink-0 border-t bg-background px-4 py-4">
        <MessageComposer
          disabled={!conversationId}
          isSending={sendMessageMutation.isPending}
          onSend={handleSendMessage}
        />
      </footer>
    </section>
  );
}
