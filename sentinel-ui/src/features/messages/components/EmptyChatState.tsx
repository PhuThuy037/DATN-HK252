import { MessageSquareText } from "lucide-react";
import { EmptyState } from "@/shared/ui/empty-state";

type EmptyChatStateProps = {
  title?: string;
  description?: string;
};

export function EmptyChatState({
  title = "No messages yet",
  description = "Send a message to start this conversation.",
}: EmptyChatStateProps) {
  return (
    <EmptyState
      description={description}
      icon={<MessageSquareText className="h-5 w-5" />}
      title={title}
    />
  );
}
