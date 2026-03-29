import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useConversations } from "@/features/conversations/hooks/useConversations";
import { useConversation } from "@/features/conversations/hooks/useConversation";
import { EmptyChatState } from "@/features/messages/components/EmptyChatState";
import { MessageComposer } from "@/features/messages/components/MessageComposer";
import { MessageList } from "@/features/messages/components/MessageList";
import { useInfiniteMessages } from "@/features/messages/hooks/useInfiniteMessages";
import { useSendMessage } from "@/features/messages/hooks/useSendMessage";
import { useChatUiStore } from "@/features/messages/store/chatUiStore";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppLoadingState } from "@/shared/ui/app-loading-state";
import { AppPageHeader } from "@/shared/ui/app-page-header";
import { Card } from "@/shared/ui/card";
import { toast } from "@/shared/ui/use-toast";
import type { MessageListItem } from "@/shared/types";

type FailedMessageItem = {
  id: string;
  content: string;
  created_at: string;
  retrying: boolean;
};

function getHttpStatusFromError(error: unknown): number | null {
  if (typeof error !== "object" || error === null) {
    return null;
  }

  const directStatus = (error as { status?: unknown }).status;
  if (typeof directStatus === "number" && Number.isFinite(directStatus)) {
    return directStatus;
  }

  const response = (error as { response?: { status?: unknown } }).response;
  const responseStatus = response?.status;
  if (typeof responseStatus === "number" && Number.isFinite(responseStatus)) {
    return responseStatus;
  }

  return null;
}

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
  const messagesQuery = useInfiniteMessages(conversationId);
  const sendMessageMutation = useSendMessage();

  const conversations = useMemo(
    () => conversationsQuery.data?.items ?? [],
    [conversationsQuery.data?.items]
  );
  const messages = useMemo(
    () =>
      (messagesQuery.data?.pages ?? [])
        .slice()
        .reverse()
        .flatMap((page) => page.items),
    [messagesQuery.data?.pages]
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
  const conversationErrorStatus = getHttpStatusFromError(conversationQuery.error);

  useEffect(() => {
    if (conversationId) {
      return;
    }
    if (
      conversationsQuery.isLoading ||
      conversationsQuery.isFetching ||
      !conversationsQuery.isFetched
    ) {
      return;
    }
    if (conversationsQuery.isError) {
      return;
    }

    if (conversations.length > 0) {
      navigate(`/app/chat/${conversations[0].id}`, { replace: true });
    }
  }, [
    conversationId,
    conversations,
    conversationsQuery.isError,
    conversationsQuery.isFetched,
    conversationsQuery.isFetching,
    conversationsQuery.isLoading,
    navigate,
  ]);

  useEffect(() => {
    if (!conversationId || !conversationQuery.isError) {
      return;
    }
    if (conversationErrorStatus === 403 || conversationErrorStatus === 404) {
      clearSelectedMessageId();
      navigate("/app/chat", { replace: true });
    }
  }, [
    clearSelectedMessageId,
    conversationErrorStatus,
    conversationId,
    conversationQuery.isError,
    navigate,
  ]);

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

  if (!conversationId) {
    return (
      <section className="flex h-full items-center justify-center p-6">
        <div className="w-full max-w-xl">
          {conversationsQuery.isLoading && (
            <AppLoadingState
              description="Loading recent conversations for this workspace."
              title="Loading conversations"
            />
          )}

          {conversationsQuery.isError && (
            <AppAlert
              description="We couldn't load the conversation list. Please try again."
              title="Conversation list unavailable"
              variant="error"
            />
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
    if (conversationErrorStatus === 403 || conversationErrorStatus === 404) {
      return (
        <section className="flex h-full items-center justify-center p-6">
          <div className="w-full max-w-xl">
            <AppLoadingState
              description="Conversation is unavailable. Returning to the conversation list."
              title="Refreshing chat workspace"
            />
          </div>
        </section>
      );
    }
    return (
      <section className="flex h-full items-center justify-center p-6">
        <div className="w-full max-w-xl">
          <AppAlert
            description="This conversation does not exist or you do not have access."
            title="Conversation not found"
            variant="error"
          />
        </div>
      </section>
    );
  }

  return (
    <section className="flex h-full min-h-0 flex-col bg-[linear-gradient(180deg,rgba(248,250,252,0.96),rgba(255,255,255,1))]">
      <header className="shrink-0 border-b border-border/70 bg-background/80 px-5 py-4 backdrop-blur lg:px-6">
        <AppPageHeader
          meta={`Conversation ID: ${conversationId}`}
          subtitle="Select any message to inspect its compliance summary and matched rules."
          title={
            conversationQuery.isLoading
              ? "Loading conversation"
              : conversationQuery.data?.title?.trim() || "Untitled conversation"
          }
        />
      </header>

      <div className="min-h-0 flex-1 px-3 py-3 lg:px-4 lg:py-4">
        <Card className="h-full overflow-hidden rounded-[30px] border-border/80 bg-background/88 shadow-app-md">
          <MessageList
            failedMessageIds={failedMessageIds}
            isError={messagesQuery.isError}
            isLoading={messagesQuery.isLoading}
            isFetchingMore={messagesQuery.isFetchingNextPage}
            isSending={sendMessageMutation.isPending}
            messages={mergedMessages}
            hasMore={Boolean(messagesQuery.hasNextPage)}
            onLoadMore={handleLoadOlderMessages}
            onRetryMessage={handleRetryFailedMessage}
            onSelectMessage={handleSelectMessage}
            retryingMessageIds={retryingMessageIds}
            selectedMessageId={selectedMessageId}
          />
        </Card>
      </div>

      <footer className="shrink-0 border-t border-border/70 bg-background/85 px-3 py-3 backdrop-blur lg:px-4 lg:py-4">
        <MessageComposer
          disabled={!conversationId}
          isSending={sendMessageMutation.isPending}
          onSend={handleSendMessage}
        />
      </footer>
    </section>
  );
}
