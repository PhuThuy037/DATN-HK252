import { memo, useEffect, useState } from "react";
import { AlertCircle, Check, Copy, Loader2, RotateCcw } from "lucide-react";
import { MarkdownRenderer } from "@/features/messages/components/MarkdownRenderer";
import { cn } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { toast } from "@/shared/ui/use-toast";
import type { MessageListItem } from "@/shared/types";

type GroupPosition = "single" | "first" | "middle" | "last";

const BLOCKED_PLACEHOLDER = "Nội dung đã bị chặn bởi compliance policy.";

type MessageBubbleProps = {
  message: MessageListItem;
  isSelected?: boolean;
  onSelect?: (messageId: string) => void;
  isFailed?: boolean;
  isSending?: boolean;
  onRetry?: () => void;
  groupPosition?: GroupPosition;
};

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function MessageBubbleComponent({
  message,
  isSelected = false,
  onSelect,
  isFailed = false,
  isSending = false,
  onRetry,
  groupPosition = "single",
}: MessageBubbleProps) {
  const finalAction = (message as { final_action?: string | null }).final_action;
  const isBlocked = message.state === "blocked" || finalAction === "block";
  const isMasked = message.state === "masked" || finalAction === "mask";
  const isUser = message.role === "user" || isBlocked;

  let content = "[No content]";
  if (isBlocked) {
    content = BLOCKED_PLACEHOLDER;
  } else if (isMasked) {
    content = message.content_masked ?? message.content ?? "[No content]";
  } else {
    content = message.content ?? message.content_masked ?? "[No content]";
  }
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) {
      return;
    }
    const timer = window.setTimeout(() => setCopied(false), 1500);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const handleCopy = async () => {
    if (!content || content === "[No content]" || isBlocked) {
      return;
    }
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
    } catch {
      toast({
        title: "Copy failed",
        description: "Unable to copy message content.",
        variant: "destructive",
      });
    }
  };

  return (
    <div className={cn("group flex w-full", isUser ? "justify-end" : "justify-start")}>
      <Card
        className={cn(
          "max-w-[70%] cursor-pointer px-4 py-3 shadow-sm transition-colors",
          isUser
            ? "border-transparent bg-zinc-900 text-zinc-50"
            : "bg-zinc-100 text-zinc-900",
          groupPosition === "single" &&
            (isUser ? "rounded-2xl rounded-br-md" : "rounded-2xl rounded-bl-md"),
          groupPosition === "first" &&
            (isUser ? "rounded-2xl rounded-br-md" : "rounded-2xl rounded-bl-md"),
          groupPosition === "middle" &&
            (isUser ? "rounded-2xl rounded-r-md" : "rounded-2xl rounded-l-md"),
          groupPosition === "last" &&
            (isUser ? "rounded-2xl rounded-tr-md" : "rounded-2xl rounded-tl-md"),
          isSelected && "ring-2 ring-primary/40"
        )}
        onClick={() => onSelect?.(message.id)}
      >
        <div className="mb-2 flex items-center justify-end gap-1 opacity-0 transition-opacity group-hover:opacity-100">
          <Button
            aria-label="Copy message"
            className={cn(
              "h-7 w-7",
              isUser ? "text-zinc-100 hover:bg-zinc-800" : "hover:bg-zinc-200"
            )}
            onClick={(event) => {
              event.stopPropagation();
              void handleCopy();
            }}
            size="icon"
            type="button"
            variant="ghost"
          >
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          </Button>
        </div>

        {isUser ? (
          <p className="whitespace-pre-wrap break-words text-sm leading-6">{content}</p>
        ) : (
          <MarkdownRenderer content={content} />
        )}

        <div className="mt-2 flex items-center justify-between gap-2">
          <p
            className={cn(
              "text-[11px]",
              isUser ? "text-zinc-300" : "text-muted-foreground"
            )}
          >
            {formatTime(message.created_at)}
          </p>

          <div className="flex items-center gap-2">
            {isBlocked && (
              <Badge className="border-red-300/70 bg-red-50 px-2 py-0 text-[10px] text-red-700">
                Blocked
              </Badge>
            )}

            {isSending && (
              <span
                className={cn(
                  "inline-flex items-center gap-1 text-[11px]",
                  isUser ? "text-zinc-300" : "text-muted-foreground"
                )}
              >
                <Loader2 className="h-3 w-3 animate-spin" />
                Sending...
              </span>
            )}

            {isFailed && (
              <>
                <Badge className="border-destructive/30 bg-destructive/10 px-2 py-0 text-[10px] text-destructive">
                  <AlertCircle className="mr-1 h-3 w-3" />
                  Failed
                </Badge>
                <Button
                  className="h-7 px-2 text-xs"
                  onClick={(event) => {
                    event.stopPropagation();
                    onRetry?.();
                  }}
                  size="sm"
                  type="button"
                  variant="outline"
                >
                  <RotateCcw className="mr-1 h-3 w-3" />
                  Retry
                </Button>
              </>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}

function areEqual(prev: MessageBubbleProps, next: MessageBubbleProps) {
  return (
    prev.message.id === next.message.id &&
    prev.message.content === next.message.content &&
    prev.message.content_masked === next.message.content_masked &&
    prev.message.state === next.message.state &&
    prev.message.role === next.message.role &&
    prev.message.created_at === next.message.created_at &&
    prev.isSelected === next.isSelected &&
    prev.isFailed === next.isFailed &&
    prev.isSending === next.isSending &&
    prev.groupPosition === next.groupPosition &&
    prev.onSelect === next.onSelect &&
    prev.onRetry === next.onRetry
  );
}

export const MessageBubble = memo(MessageBubbleComponent, areEqual);
