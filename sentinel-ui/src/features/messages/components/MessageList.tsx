import { ChevronDown } from "lucide-react";
import {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type UIEvent,
} from "react";
import { MessageBubble } from "@/features/messages/components/MessageBubble";
import { EmptyChatState } from "@/features/messages/components/EmptyChatState";
import { MessageSkeleton } from "@/features/messages/components/MessageSkeleton";
import { TypingIndicator } from "@/features/messages/components/TypingIndicator";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppButton } from "@/shared/ui/app-button";
import { ScrollArea } from "@/shared/ui/scroll-area";
import type { MessageListItem } from "@/shared/types";

const TOP_LOAD_THRESHOLD_PX = 48;
const BOTTOM_STICK_THRESHOLD_PX = 96;
const SCROLL_TO_LATEST_THRESHOLD_PX = 160;

type MessageListProps = {
  messages: MessageListItem[];
  selectedMessageId: string | null;
  onSelectMessage: (messageId: string) => void;
  isLoading?: boolean;
  isError?: boolean;
  isSending?: boolean;
  hasMore?: boolean;
  isFetchingMore?: boolean;
  onLoadMore?: () => Promise<unknown> | void;
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
  hasMore = false,
  isFetchingMore = false,
  onLoadMore,
  failedMessageIds = [],
  retryingMessageIds = [],
  onRetryMessage,
}: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [showScrollToLatest, setShowScrollToLatest] = useState(false);
  const prevMessageCountRef = useRef(0);
  const prevFirstMessageIdRef = useRef<string | null>(null);
  const prevLastMessageIdRef = useRef<string | null>(null);
  const isLoadingMoreRef = useRef(false);
  const shouldStickToBottomRef = useRef(true);
  const pendingPrependRef = useRef<{
    prevScrollTop: number;
    prevScrollHeight: number;
    firstMessageId: string | null;
  } | null>(null);
  const failedSet = useMemo(() => new Set(failedMessageIds), [failedMessageIds]);
  const retryingSet = useMemo(
    () => new Set(retryingMessageIds),
    [retryingMessageIds]
  );

  const firstMessageId = messages[0]?.id ?? null;
  const lastMessageId = messages[messages.length - 1]?.id ?? null;

  const syncBottomState = useCallback((el: HTMLDivElement) => {
    const distanceToBottom = el.scrollHeight - (el.scrollTop + el.clientHeight);
    shouldStickToBottomRef.current = distanceToBottom <= BOTTOM_STICK_THRESHOLD_PX;
    setShowScrollToLatest(distanceToBottom > SCROLL_TO_LATEST_THRESHOLD_PX);
  }, []);

  const handleScroll = useCallback(
    (event: UIEvent<HTMLDivElement>) => {
      const el = event.currentTarget;
      syncBottomState(el);

      if (
        !onLoadMore ||
        !hasMore ||
        isFetchingMore ||
        isLoadingMoreRef.current ||
        el.scrollTop > TOP_LOAD_THRESHOLD_PX
      ) {
        return;
      }

      pendingPrependRef.current = {
        prevScrollTop: el.scrollTop,
        prevScrollHeight: el.scrollHeight,
        firstMessageId,
      };
      isLoadingMoreRef.current = true;

      Promise.resolve(onLoadMore())
        .catch(() => {
          pendingPrependRef.current = null;
        })
        .finally(() => {
          isLoadingMoreRef.current = false;
        });
    },
    [firstMessageId, hasMore, isFetchingMore, onLoadMore, syncBottomState]
  );

  useEffect(() => {
    if (!isFetchingMore) {
      isLoadingMoreRef.current = false;
    }
  }, [isFetchingMore]);

  useEffect(() => {
    if (!scrollRef.current) {
      return;
    }

    const prevCount = prevMessageCountRef.current;
    const prevFirstId = prevFirstMessageIdRef.current;
    const prevLastId = prevLastMessageIdRef.current;
    const hasNewMessage = messages.length > prevMessageCountRef.current;

    if (prevCount === 0 && messages.length > 0) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "auto",
      });
    } else if (
      pendingPrependRef.current &&
      firstMessageId !== pendingPrependRef.current.firstMessageId
    ) {
      const scrollDelta =
        scrollRef.current.scrollHeight - pendingPrependRef.current.prevScrollHeight;
      scrollRef.current.scrollTo({
        top: pendingPrependRef.current.prevScrollTop + scrollDelta,
        behavior: "auto",
      });
      pendingPrependRef.current = null;
    } else if (
      hasNewMessage &&
      prevFirstId === firstMessageId &&
      prevLastId !== lastMessageId &&
      shouldStickToBottomRef.current
    ) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }

    prevMessageCountRef.current = messages.length;
    prevFirstMessageIdRef.current = firstMessageId;
    prevLastMessageIdRef.current = lastMessageId;
    syncBottomState(scrollRef.current);
  }, [firstMessageId, lastMessageId, messages, syncBottomState]);

  const handleScrollToLatest = useCallback(() => {
    if (!scrollRef.current) {
      return;
    }
    shouldStickToBottomRef.current = true;
    setShowScrollToLatest(false);
    scrollRef.current.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, []);

  if (isLoading) {
    return (
      <div className="space-y-5 p-6 lg:p-7">
        <MessageSkeleton />
        <MessageSkeleton />
        <MessageSkeleton />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-6">
        <AppAlert
          description="We couldn't load messages for this conversation."
          title="Messages unavailable"
          variant="error"
        />
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="space-y-4 p-6 lg:p-7">
        <EmptyChatState />
        {isSending && (
          <p className="text-center text-xs text-muted-foreground">Sending message...</p>
        )}
      </div>
    );
  }

  return (
    <div className="relative h-full">
      <ScrollArea className="h-full" onScroll={handleScroll} ref={scrollRef}>
        <div className="space-y-3 bg-[radial-gradient(circle_at_top,_rgba(37,99,235,0.06),_transparent_35%),linear-gradient(180deg,rgba(248,250,252,0.95),rgba(255,255,255,0.98))] px-4 py-5 sm:px-5 lg:px-6 lg:py-6">
          {isFetchingMore && (
            <p className="text-center text-xs text-muted-foreground">
              Loading older messages...
            </p>
          )}

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
                className={samePrev ? "mt-2" : "mt-6 first:mt-0"}
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

          {isSending && <TypingIndicator />}
        </div>
      </ScrollArea>

      {showScrollToLatest ? (
        <div className="pointer-events-none absolute inset-x-0 bottom-4 flex justify-center">
          <AppButton
            aria-label="Jump to latest message"
            className="pointer-events-auto h-10 w-10 rounded-full border border-border/80 bg-background/95 p-0 shadow-app-md backdrop-blur"
            onClick={handleScrollToLatest}
            type="button"
            variant="secondary"
          >
            <ChevronDown className="h-4 w-4" />
          </AppButton>
        </div>
      ) : null}
    </div>
  );
}

function areEqual(prev: MessageListProps, next: MessageListProps) {
  return (
    prev.messages === next.messages &&
    prev.selectedMessageId === next.selectedMessageId &&
    prev.isLoading === next.isLoading &&
    prev.isError === next.isError &&
    prev.isSending === next.isSending &&
    prev.hasMore === next.hasMore &&
    prev.isFetchingMore === next.isFetchingMore &&
    prev.onLoadMore === next.onLoadMore &&
    prev.failedMessageIds === next.failedMessageIds &&
    prev.retryingMessageIds === next.retryingMessageIds &&
    prev.onSelectMessage === next.onSelectMessage &&
    prev.onRetryMessage === next.onRetryMessage
  );
}

export const MessageList = memo(MessageListComponent, areEqual);
