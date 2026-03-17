import { Card } from "@/shared/ui/card";

export function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <Card
        aria-live="polite"
        className="w-fit rounded-2xl rounded-bl-md border bg-background px-4 py-3"
      >
        <div className="flex items-center gap-1.5" role="status">
          <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.2s]" />
          <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.1s]" />
          <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground" />
          <span className="sr-only">Assistant is typing</span>
        </div>
      </Card>
    </div>
  );
}
