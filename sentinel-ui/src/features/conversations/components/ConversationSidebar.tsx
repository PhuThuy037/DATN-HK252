import { useMemo, useState } from "react";
import { LogOut, MessageSquarePlus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  extractAuthErrorMessage,
  logout,
} from "@/features/auth/api/authApi";
import { useAuthStore } from "@/features/auth/store/authStore";
import { ConversationListItem } from "@/features/conversations/components/ConversationListItem";
import { useConversations } from "@/features/conversations/hooks/useConversations";
import { useCreateConversation } from "@/features/conversations/hooks/useCreateConversation";
import { useDeleteConversation } from "@/features/conversations/hooks/useDeleteConversation";
import { useUpdateConversation } from "@/features/conversations/hooks/useUpdateConversation";
import { cn } from "@/shared/lib/utils";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { toast } from "@/shared/ui/use-toast";
import type { ConversationListItem as ConversationListItemType } from "@/shared/types";

type ConversationSidebarProps = {
  activeConversationId?: string;
  className?: string;
  onConversationSelect?: () => void;
};

export function ConversationSidebar({
  activeConversationId,
  className,
  onConversationSelect,
}: ConversationSidebarProps) {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const refreshToken = useAuthStore((state) => state.refreshToken);
  const clearAuth = useAuthStore((state) => state.clearAuth);

  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const conversationsQuery = useConversations();
  const createConversationMutation = useCreateConversation();
  const updateConversationMutation = useUpdateConversation();
  const deleteConversationMutation = useDeleteConversation();

  const conversations = useMemo(
    () => conversationsQuery.data?.items ?? [],
    [conversationsQuery.data?.items]
  );

  const isMutating =
    createConversationMutation.isPending ||
    updateConversationMutation.isPending ||
    deleteConversationMutation.isPending;

  const handleOpenConversation = (conversationId: string) => {
    navigate(`/app/chat/${conversationId}`);
    onConversationSelect?.();
  };

  const handleCreateConversation = async () => {
    try {
      const created = await createConversationMutation.mutateAsync({
        title: "New conversation",
      });
      toast({
        title: "Conversation created",
        description: "New conversation is ready.",
        variant: "success",
      });
      navigate(`/app/chat/${created.id}`);
      onConversationSelect?.();
    } catch (error) {
      toast({
        title: "Create failed",
        description: extractAuthErrorMessage(error),
        variant: "destructive",
      });
    }
  };

  const handleRenameConversation = async (item: ConversationListItemType) => {
    const nextTitle = window.prompt(
      "Rename conversation",
      item.title?.trim() || "Untitled conversation"
    );

    if (!nextTitle || !nextTitle.trim()) {
      return;
    }

    try {
      await updateConversationMutation.mutateAsync({
        conversationId: item.id,
        payload: { title: nextTitle.trim() },
      });
      toast({
        title: "Conversation renamed",
        description: "Title updated successfully.",
        variant: "success",
      });
    } catch (error) {
      toast({
        title: "Rename failed",
        description: extractAuthErrorMessage(error),
        variant: "destructive",
      });
    }
  };

  const handleArchiveConversation = async (item: ConversationListItemType) => {
    try {
      await updateConversationMutation.mutateAsync({
        conversationId: item.id,
        payload: { status: "archived" },
      });
      toast({
        title: "Conversation archived",
        description: "Conversation moved out of active list.",
        variant: "success",
      });

      if (activeConversationId === item.id) {
        navigate("/app/chat");
        onConversationSelect?.();
      }
    } catch (error) {
      toast({
        title: "Archive failed",
        description: extractAuthErrorMessage(error),
        variant: "destructive",
      });
    }
  };

  const handleDeleteConversation = async (item: ConversationListItemType) => {
    const confirmed = window.confirm("Delete this conversation?");
    if (!confirmed) {
      return;
    }

    try {
      await deleteConversationMutation.mutateAsync(item.id);
      toast({
        title: "Conversation deleted",
        description: "Conversation removed successfully.",
        variant: "success",
      });

      if (activeConversationId === item.id) {
        navigate("/app/chat");
        onConversationSelect?.();
      }
    } catch (error) {
      toast({
        title: "Delete failed",
        description: extractAuthErrorMessage(error),
        variant: "destructive",
      });
    }
  };

  const handleLogout = async () => {
    setIsLoggingOut(true);

    try {
      if (refreshToken) {
        await logout({ refresh_token: refreshToken });
      }
    } catch {
      // Always clear local auth even when API logout fails.
    } finally {
      clearAuth();
      navigate("/login");
      setIsLoggingOut(false);
    }
  };

  return (
    <aside className={cn("flex h-full flex-col border-r bg-muted/30 p-3", className)}>
      <div className="mb-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h1 className="text-base font-semibold">Sentinel Workspace</h1>
            <p className="text-xs text-muted-foreground">{user?.email ?? "User"}</p>
          </div>
          <Button
            disabled={isLoggingOut}
            onClick={() => void handleLogout()}
            size="sm"
            type="button"
            variant="outline"
          >
            <LogOut className="mr-1 h-3.5 w-3.5" />
            Logout
          </Button>
        </div>
      </div>

      <Button
        className="mb-3 w-full justify-start"
        disabled={isMutating}
        onClick={() => void handleCreateConversation()}
        type="button"
      >
        <MessageSquarePlus className="mr-2 h-4 w-4" />
        New conversation
      </Button>

      <Card className="min-h-0 flex-1 overflow-hidden p-2">
        <ScrollArea className="h-full">
          <div className="space-y-2.5 pb-2">
            {conversationsQuery.isLoading && (
              <p className="px-2 py-1 text-xs text-muted-foreground">
                Loading conversations...
              </p>
            )}

            {conversationsQuery.isError && (
              <p className="px-2 py-1 text-xs text-destructive">
                Failed to load conversations.
              </p>
            )}

            {!conversationsQuery.isLoading &&
              !conversationsQuery.isError &&
              conversations.length === 0 && (
                <div className="rounded-lg border border-dashed px-3 py-4 text-center">
                  <p className="text-sm font-medium">No conversations</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Create a new conversation to get started.
                  </p>
                </div>
              )}

            {conversations.map((item) => (
              <ConversationListItem
                isActive={activeConversationId === item.id}
                item={item}
                key={item.id}
                onArchive={(value) => void handleArchiveConversation(value)}
                onDelete={(value) => void handleDeleteConversation(value)}
                onOpen={handleOpenConversation}
                onRename={(value) => void handleRenameConversation(value)}
              />
            ))}
          </div>
        </ScrollArea>
      </Card>
    </aside>
  );
}
