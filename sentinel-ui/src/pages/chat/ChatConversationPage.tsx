import { useParams } from "react-router-dom";
import { ChatWorkspace } from "@/features/messages/ChatWorkspace";

export function ChatConversationPage() {
  const { conversationId } = useParams();
  return <ChatWorkspace conversationId={conversationId} />;
}
