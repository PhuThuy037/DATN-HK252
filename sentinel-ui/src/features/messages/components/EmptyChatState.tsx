type EmptyChatStateProps = {
  title?: string;
  description?: string;
};

export function EmptyChatState({
  title = "No messages yet",
  description = "Send a message to start this conversation.",
}: EmptyChatStateProps) {
  return (
    <div className="rounded-md border border-dashed p-6 text-center">
      <p className="text-sm font-medium">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
    </div>
  );
}
