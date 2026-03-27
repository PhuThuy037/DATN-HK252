import { Card } from "@/shared/ui/card";

export function TypingIndicator() {
  return (
    <div className="flex justify-start pt-3">
      <Card
        aria-live="polite"
        className="w-fit rounded-[24px] rounded-bl-lg border border-border/80 bg-background/95 px-4 py-3 shadow-app-sm"
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
