import { FormEvent, KeyboardEvent, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { AppButton } from "@/shared/ui/app-button";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { Textarea } from "@/shared/ui/textarea";

type MessageComposerProps = {
  disabled?: boolean;
  isSending?: boolean;
  onSend: (content: string) => Promise<void> | void;
};

export function MessageComposer({
  disabled = false,
  isSending = false,
  onSend,
}: MessageComposerProps) {
  const [content, setContent] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const resizeTextarea = () => {
    if (!textareaRef.current) {
      return;
    }
    textareaRef.current.style.height = "auto";
    textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
  };

  const submit = async () => {
    const trimmed = content.trim();
    if (!trimmed || disabled || isSending) {
      return;
    }

    try {
      await onSend(trimmed);
      setContent("");
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }
    } catch {
      // Keep current input when send fails so user can retry/edit.
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await submit();
  };

  const handleKeyDown = async (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) {
      return;
    }

    event.preventDefault();
    await submit();
  };

  return (
    <form
      aria-busy={isSending}
      className="space-y-3"
      onSubmit={handleSubmit}
    >
      <AppSectionCard
        className="rounded-[26px] border-border/80 bg-background/95 p-3 shadow-app-md"
        contentClassName="space-y-3"
      >
        <Textarea
          className="max-h-[180px] min-h-[64px] resize-none rounded-[20px] border-0 bg-muted/35 px-4 py-4 text-sm leading-6 shadow-none"
          disabled={disabled || isSending}
          onChange={(event) => {
            setContent(event.target.value);
            resizeTextarea();
          }}
          onKeyDown={(event) => void handleKeyDown(event)}
          placeholder="Type your message..."
          ref={textareaRef}
          value={content}
        />

        <div className="flex items-end justify-between gap-3">
          <p className="text-[11px] text-muted-foreground">
            Press Enter to send. Use Shift+Enter for a new line.
          </p>
          <AppButton
            className="shrink-0"
            disabled={disabled || isSending || !content.trim()}
            type="submit"
          >
            {isSending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Sending...
              </>
            ) : (
              "Send"
            )}
          </AppButton>
        </div>
      </AppSectionCard>
    </form>
  );
}
