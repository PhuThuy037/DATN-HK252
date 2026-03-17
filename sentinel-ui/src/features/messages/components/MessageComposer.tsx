import { FormEvent, KeyboardEvent, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/shared/ui/button";
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
      <Textarea
        className="max-h-[180px] min-h-[52px] resize-none rounded-xl px-4 py-3"
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

      <div className="flex justify-end">
        <Button
          disabled={disabled || isSending || !content.trim()}
          type="submit"
        >
          {isSending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Sending...
            </>
          ) : (
            "Send"
          )}
        </Button>
      </div>
    </form>
  );
}
