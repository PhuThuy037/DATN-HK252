import { memo, useEffect, useState } from "react";
import { Check, Copy, Loader2, RotateCcw, ShieldAlert, ShieldCheck, ShieldEllipsis } from "lucide-react";
import { MarkdownRenderer } from "@/features/messages/components/MarkdownRenderer";
import { cn } from "@/shared/lib/utils";
import { AppButton } from "@/shared/ui/app-button";
import { Card } from "@/shared/ui/card";
import { StatusBadge } from "@/shared/ui/status-badge";
import { toast } from "@/shared/ui/use-toast";
import type { MessageListItem } from "@/shared/types";

type GroupPosition = "single" | "first" | "middle" | "last";

const BLOCKED_PLACEHOLDER = "Content was blocked by the active compliance policy.";

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

function getActionState(message: MessageListItem) {
  const finalAction = String(message.final_action ?? "").trim().toLowerCase();
  if (message.blocked || message.state === "blocked" || finalAction === "block") {
    return "block";
  }
  if (message.state === "masked" || finalAction === "mask") {
    return "mask";
  }
  if (finalAction === "allow") {
    return "allow";
  }
  return null;
}

function getActionIcon(action: "allow" | "mask" | "block" | null, isUser: boolean) {
  const className = cn("h-3.5 w-3.5", isUser ? "text-zinc-200" : "text-current");
  if (action === "allow") {
    return <ShieldCheck className={className} />;
  }
  if (action === "mask") {
    return <ShieldEllipsis className={className} />;
  }
  if (action === "block") {
    return <ShieldAlert className={className} />;
  }
  return null;
}

function getBubbleRadiusClass(isUser: boolean, groupPosition: GroupPosition) {
  if (groupPosition === "middle") {
    return isUser ? "rounded-[24px] rounded-r-lg" : "rounded-[24px] rounded-l-lg";
  }
  if (groupPosition === "first") {
    return isUser ? "rounded-[24px] rounded-br-lg" : "rounded-[24px] rounded-bl-lg";
  }
  if (groupPosition === "last") {
    return isUser ? "rounded-[24px] rounded-tr-lg" : "rounded-[24px] rounded-tl-lg";
  }
  return isUser ? "rounded-[24px] rounded-br-lg" : "rounded-[24px] rounded-bl-lg";
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
  const actionState = getActionState(message);
  const isBlocked = actionState === "block";
  const isMasked = actionState === "mask";
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  let content = "[No content]";
  if (isBlocked) {
    content = BLOCKED_PLACEHOLDER;
  } else if (isMasked) {
    content = message.content_masked ?? message.content ?? "[No content]";
  } else {
    content = message.content ?? message.content_masked ?? "[No content]";
  }

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
      <div
        className={cn(
          "flex w-full flex-col",
          isUser ? "max-w-[84%] items-end md:max-w-[38rem]" : "max-w-[92%] items-start md:max-w-[46rem]"
        )}
      >
        <Card
          className={cn(
            "w-full cursor-pointer border shadow-app-sm transition-all",
            isUser
              ? "border-slate-900/85 bg-slate-900 text-slate-50"
              : "border-border/80 bg-white/95 text-slate-900",
            getBubbleRadiusClass(isUser, groupPosition),
            isSelected && "ring-2 ring-primary/35 ring-offset-2",
            isUser ? "px-4 py-3.5 md:px-4" : "px-4 py-4 md:px-5"
          )}
          onClick={() => onSelect?.(message.id)}
        >
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2.5">
              <span
                className={cn(
                  "text-[11px] font-semibold uppercase tracking-[0.14em]",
                  isUser ? "text-zinc-300" : "text-muted-foreground"
                )}
              >
                  {isUser ? "You" : "Assistant"}
              </span>

              {actionState ? (
                <span className="inline-flex items-center gap-1.5">
                  {getActionIcon(actionState, isUser)}
                  <StatusBadge
                    className={cn(
                      "px-2.5 py-1 text-[10px]",
                      isUser && actionState === "allow" && "border-white/20 bg-white/10 text-white",
                      isUser && actionState === "mask" && "border-amber-300/25 bg-amber-300/12 text-amber-100",
                      isUser && actionState === "block" && "border-rose-300/25 bg-rose-300/12 text-rose-100"
                    )}
                    status={actionState}
                  />
                </span>
              ) : null}
            </div>

            <div className="min-w-0">
              {isUser ? (
                <p className="whitespace-pre-wrap break-words text-sm leading-7 text-slate-50/95">
                  {content}
                </p>
              ) : (
                <div className="text-sm leading-7 text-slate-900">
                  <MarkdownRenderer content={content} />
                </div>
              )}
            </div>

            {(message.blocked_reason && isBlocked) || isFailed || isSending ? (
              <div className={cn("space-y-2 border-t pt-3", isUser ? "border-white/10" : "border-border/70")}>
                {message.blocked_reason && isBlocked ? (
                  <p className={cn("text-xs", isUser ? "text-rose-100/80" : "text-muted-foreground")}>
                    Reason: {message.blocked_reason}
                  </p>
                ) : null}

                <div className="flex flex-wrap items-center gap-2">
                  {isSending && (
                    <span
                      className={cn(
                        "inline-flex items-center gap-1.5 text-[11px]",
                        isUser ? "text-zinc-300" : "text-muted-foreground"
                      )}
                    >
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Sending...
                    </span>
                  )}

                  {isFailed && (
                    <>
                      <StatusBadge
                        className="gap-1 border-danger-border bg-danger-muted px-2.5 py-1 text-[10px] text-danger"
                        label="Failed"
                        tone="danger"
                      />
                      <AppButton
                        className="h-8 rounded-full px-3 text-xs"
                        onClick={(event) => {
                          event.stopPropagation();
                          onRetry?.();
                        }}
                        size="sm"
                        type="button"
                        variant="secondary"
                      >
                        <RotateCcw className="h-3 w-3" />
                        Retry
                      </AppButton>
                    </>
                  )}
                </div>
              </div>
            ) : null}

            <div
              className={cn(
                "flex items-center justify-between gap-3 border-t pt-2.5",
                isUser ? "border-white/10" : "border-border/70"
              )}
            >
              <span
                className={cn(
                  "text-[11px]",
                  isUser ? "text-slate-300/80" : "text-muted-foreground"
                )}
              >
                {formatTime(message.created_at)}
              </span>

              <AppButton
                aria-label="Copy message"
                className={cn(
                  "h-8 w-8 shrink-0 rounded-full px-0 opacity-0 transition-opacity group-hover:opacity-100",
                  isUser
                    ? "border-white/10 bg-white/5 text-zinc-100 hover:bg-white/10"
                    : "border-border/70 bg-background text-muted-foreground hover:text-foreground",
                  copied && "opacity-100"
                )}
                onClick={(event) => {
                  event.stopPropagation();
                  void handleCopy();
                }}
                size="icon"
                type="button"
                variant="secondary"
              >
                {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              </AppButton>
            </div>
          </div>
        </Card>
      </div>
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
    prev.message.final_action === next.message.final_action &&
    prev.message.risk_score === next.message.risk_score &&
    prev.message.blocked === next.message.blocked &&
    prev.message.blocked_reason === next.message.blocked_reason &&
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
