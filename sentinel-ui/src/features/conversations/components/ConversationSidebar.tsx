import { useMemo, useState } from "react";
import {
  LogOut,
  MessageSquarePlus,
  Scale,
  MessagesSquare,
  WandSparkles,
  FileText,
  SlidersHorizontal,
} from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
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
import { useRuleSetStore } from "@/features/rules/store/ruleSetStore";
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
  const location = useLocation();
  const user = useAuthStore((state) => state.user);
  const refreshToken = useAuthStore((state) => state.refreshToken);
  const clearAuth = useAuthStore((state) => state.clearAuth);
  const currentRuleSet = useRuleSetStore((state) => state.currentRuleSet);
  const clearCurrentRuleSet = useRuleSetStore((state) => state.clearCurrentRuleSet);
  const setRuleSetResolved = useRuleSetStore((state) => state.setRuleSetResolved);

  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [renamingConversationId, setRenamingConversationId] = useState<string | null>(
    null
  );
  const [renameDraft, setRenameDraft] = useState("");
  const [renameError, setRenameError] = useState<string | null>(null);

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
  const CONVERSATION_TITLE_MAX_LENGTH = 300;

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

  const isRulesRoute = location.pathname.startsWith("/app/settings/rules");
  const isSystemPromptRoute = location.pathname.startsWith(
    "/app/settings/system-prompt"
  );
  const isSuggestionsRoute = location.pathname.startsWith("/app/suggestions");
  const isPoliciesRoute = location.pathname.startsWith("/app/policies");
  const isChatRoute = location.pathname.startsWith("/app/chat");

  const startRenameConversation = (item: ConversationListItemType) => {
    setRenamingConversationId(item.id);
    setRenameDraft(item.title?.trim() || "");
    setRenameError(null);
  };

  const cancelRenameConversation = () => {
    setRenamingConversationId(null);
    setRenameDraft("");
    setRenameError(null);
  };

  const resolveRenameErrorMessage = (error: unknown) => {
    const message = extractAuthErrorMessage(error);
    const normalized = String(message || "").toLowerCase();
    if (normalized.includes("at most 300") || normalized.includes("max_length")) {
      return "Conversation name is too long.";
    }
    if (normalized.includes("empty") || normalized.includes("blank")) {
      return "Conversation name cannot be empty.";
    }
    return message || "Unable to rename conversation.";
  };

  const updateRenameDraft = (value: string) => {
    setRenameDraft(value);
    const trimmed = value.trim();
    if (!trimmed) {
      setRenameError("Conversation name cannot be empty.");
      return;
    }
    if (trimmed.length > CONVERSATION_TITLE_MAX_LENGTH) {
      setRenameError("Conversation name is too long.");
      return;
    }
    setRenameError(null);
  };

  const submitRenameConversation = async () => {
    if (!renamingConversationId) {
      return;
    }
    const normalized = renameDraft.trim();
    if (!normalized) {
      setRenameError("Conversation name cannot be empty.");
      return;
    }
    if (normalized.length > CONVERSATION_TITLE_MAX_LENGTH) {
      setRenameError("Conversation name is too long.");
      return;
    }

    try {
      await updateConversationMutation.mutateAsync({
        conversationId: renamingConversationId,
        payload: { title: normalized },
      });
      toast({
        title: "Conversation renamed",
        description: "Title updated successfully.",
        variant: "success",
      });
      cancelRenameConversation();
    } catch (error) {
      const message = resolveRenameErrorMessage(error);
      setRenameError(message);
      toast({
        title: "Rename failed",
        description: message,
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
      clearCurrentRuleSet();
      setRuleSetResolved(false);
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
            {currentRuleSet?.name && (
              <p className="text-xs text-muted-foreground">
                Rule set: {currentRuleSet.name}
              </p>
            )}
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

      <div className="mb-3 grid grid-cols-1 gap-2">
        <Button
          className="justify-start"
          onClick={() => {
            navigate("/app/chat");
            onConversationSelect?.();
          }}
          size="sm"
          type="button"
          variant={isChatRoute ? "default" : "outline"}
        >
          <MessagesSquare className="mr-2 h-4 w-4" />
          Chat
        </Button>
        <Button
          className="justify-start"
          onClick={() => {
            navigate("/app/settings/rules");
            onConversationSelect?.();
          }}
          size="sm"
          type="button"
          variant={isRulesRoute ? "default" : "outline"}
        >
          <Scale className="mr-2 h-4 w-4" />
          Rules
        </Button>
        <Button
          className="justify-start"
          onClick={() => {
            navigate("/app/settings/system-prompt");
            onConversationSelect?.();
          }}
          size="sm"
          type="button"
          variant={isSystemPromptRoute ? "default" : "outline"}
        >
          <SlidersHorizontal className="mr-2 h-4 w-4" />
          System Prompt
        </Button>
        <Button
          className="justify-start"
          onClick={() => {
            navigate("/app/suggestions");
            onConversationSelect?.();
          }}
          size="sm"
          type="button"
          variant={isSuggestionsRoute ? "default" : "outline"}
        >
          <WandSparkles className="mr-2 h-4 w-4" />
          Suggestions
        </Button>
        <Button
          className="justify-start"
          onClick={() => {
            navigate("/app/policies");
            onConversationSelect?.();
          }}
          size="sm"
          type="button"
          variant={isPoliciesRoute ? "default" : "outline"}
        >
          <FileText className="mr-2 h-4 w-4" />
          Policies
        </Button>
      </div>

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
                isRenameSubmitting={
                  updateConversationMutation.isPending &&
                  renamingConversationId === item.id
                }
                isRenaming={renamingConversationId === item.id}
                item={item}
                key={item.id}
                onArchive={(value) => void handleArchiveConversation(value)}
                onDelete={(value) => void handleDeleteConversation(value)}
                onOpen={handleOpenConversation}
                onRenameCancel={cancelRenameConversation}
                onRenameChange={updateRenameDraft}
                onRenameStart={startRenameConversation}
                onRenameSubmit={() => void submitRenameConversation()}
                renameError={renamingConversationId === item.id ? renameError : null}
                renameValue={renamingConversationId === item.id ? renameDraft : ""}
              />
            ))}
          </div>
        </ScrollArea>
      </Card>
    </aside>
  );
}
