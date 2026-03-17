import { memo, useEffect, useMemo, useRef } from "react";
import { MessageBubble } from "@/features/messages/components/MessageBubble";
import { EmptyChatState } from "@/features/messages/components/EmptyChatState";
import { MessageSkeleton } from "@/features/messages/components/MessageSkeleton";
import { TypingIndicator } from "@/features/messages/components/TypingIndicator";
import { ScrollArea } from "@/shared/ui/scroll-area";
import type { MessageListItem } from "@/shared/types";

type MessageListProps = {
  messages: MessageListItem[];
  selectedMessageId: string | null;
  onSelectMessage: (messageId: string) => void;
  isLoading?: boolean;
  isError?: boolean;
  isSending?: boolean;
  failedMessageIds?: string[];
  retryingMessageIds?: string[];
  onRetryMessage?: (messageId: string) => void;
};

function MessageListComponent({
  messages,
  selectedMessageId,
  onSelectMessage,
  isLoading = false,
  isError = false,
  isSending = false,
  failedMessageIds = [],
  retryingMessageIds = [],
  onRetryMessage,
}: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const prevMessageCountRef = useRef(0);
  const failedSet = useMemo(() => new Set(failedMessageIds), [failedMessageIds]);
  const retryingSet = useMemo(
    () => new Set(retryingMessageIds),
    [retryingMessageIds]
  );

  useEffect(() => {
    if (!scrollRef.current) {
      return;
    }

    const hasNewMessage = messages.length > prevMessageCountRef.current;
    if (hasNewMessage) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
    prevMessageCountRef.current = messages.length;
  }, [messages]);

  if (isLoading) {
    return (
      <div className="space-y-4 p-6">
        <MessageSkeleton />
        <MessageSkeleton />
        <MessageSkeleton />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-6">
        <p className="text-sm text-destructive">Failed to load messages.</p>
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="space-y-4 p-6">
        <EmptyChatState />
        {isSending && (
          <p className="text-center text-xs text-muted-foreground">Sending message...</p>
        )}
      </div>
    );
  }

  return (
    <ScrollArea className="h-full" ref={scrollRef}>
      <div className="space-y-4 px-4 py-6">
        {messages.map((message, index) => {
          const prev = messages[index - 1];
          const next = messages[index + 1];
          const samePrev = prev?.role === message.role;
          const sameNext = next?.role === message.role;
          const groupPosition = samePrev
            ? sameNext
              ? "middle"
              : "last"
            : sameNext
              ? "first"
              : "single";

          return (
            <div
              className={samePrev ? "mt-1" : "mt-4 first:mt-0"}
              key={message.id}
            >
              <MessageBubble
                groupPosition={groupPosition}
                isFailed={failedSet.has(message.id)}
                isSelected={selectedMessageId === message.id}
                isSending={retryingSet.has(message.id)}
                message={message}
                onRetry={
                  failedSet.has(message.id)
                    ? () => onRetryMessage?.(message.id)
                    : undefined
                }
                onSelect={onSelectMessage}
              />
            </div>
          );
        })}

        {isSending && (
          <TypingIndicator />
        )}
      </div>
    </ScrollArea>
  );
}

function areEqual(prev: MessageListProps, next: MessageListProps) {
  return (
    prev.messages === next.messages &&
    prev.selectedMessageId === next.selectedMessageId &&
    prev.isLoading === next.isLoading &&
    prev.isError === next.isError &&
    prev.isSending === next.isSending &&
    prev.failedMessageIds === next.failedMessageIds &&
    prev.retryingMessageIds === next.retryingMessageIds &&
    prev.onSelectMessage === next.onSelectMessage &&
    prev.onRetryMessage === next.onRetryMessage
  );
}

export const MessageList = memo(MessageListComponent, areEqual);
