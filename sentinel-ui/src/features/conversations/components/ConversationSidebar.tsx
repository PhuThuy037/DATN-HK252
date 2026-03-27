import { useMemo, useState } from "react";
import {
  LogOut,
  MessageSquarePlus,
  Scale,
  MessagesSquare,
  WandSparkles,
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
import { AppAlert } from "@/shared/ui/app-alert";
import { AppButton } from "@/shared/ui/app-button";
import { AppLoadingState } from "@/shared/ui/app-loading-state";
import { AppModal } from "@/shared/ui/app-modal";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";
import { EmptyState } from "@/shared/ui/empty-state";
import { FieldHelpText } from "@/shared/ui/field-help-text";
import { Input } from "@/shared/ui/input";
import { InlineErrorText } from "@/shared/ui/inline-error-text";
import { Label } from "@/shared/ui/label";
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
  const [renamingConversation, setRenamingConversation] = useState<ConversationListItemType | null>(null);
  const [conversationPendingDelete, setConversationPendingDelete] = useState<ConversationListItemType | null>(null);
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
  const conversationTitleMaxLength = 300;

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
  const isChatRoute = location.pathname.startsWith("/app/chat");

  const startRenameConversation = (item: ConversationListItemType) => {
    setRenamingConversation(item);
    setRenameDraft(item.title?.trim() || "");
    setRenameError(null);
  };

  const cancelRenameConversation = () => {
    setRenamingConversation(null);
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
    if (trimmed.length > conversationTitleMaxLength) {
      setRenameError("Conversation name is too long.");
      return;
    }
    setRenameError(null);
  };

  const submitRenameConversation = async () => {
    if (!renamingConversation) {
      return;
    }
    const normalized = renameDraft.trim();
    if (!normalized) {
      setRenameError("Conversation name cannot be empty.");
      return;
    }
    if (normalized.length > conversationTitleMaxLength) {
      setRenameError("Conversation name is too long.");
      return;
    }

    try {
      await updateConversationMutation.mutateAsync({
        conversationId: renamingConversation.id,
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

  const handleDeleteConversation = async () => {
    if (!conversationPendingDelete) {
      return;
    }

    try {
      await deleteConversationMutation.mutateAsync(conversationPendingDelete.id);
      toast({
        title: "Conversation deleted",
        description: "Conversation removed successfully.",
        variant: "success",
      });

      if (activeConversationId === conversationPendingDelete.id) {
        navigate("/app/chat");
        onConversationSelect?.();
      }

      setConversationPendingDelete(null);
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

  const navButtonClassName = "h-10 justify-start rounded-xl text-sm";

  return (
    <>
      <aside className={cn("flex h-full flex-col border-r bg-muted/20 p-3", className)}>
        <div className="mb-4 rounded-2xl border border-border/70 bg-background px-4 py-4 shadow-app-sm">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h1 className="text-base font-semibold">Sentinel Workspace</h1>
              <p className="truncate text-xs text-muted-foreground">{user?.email ?? "User"}</p>
              {currentRuleSet?.name && (
                <p className="truncate text-xs text-muted-foreground">
                  Rule set: {currentRuleSet.name}
                </p>
              )}
            </div>
            <AppButton
              disabled={isLoggingOut}
              onClick={() => void handleLogout()}
              size="sm"
              type="button"
              variant="secondary"
            >
              <LogOut className="h-3.5 w-3.5" />
              Logout
            </AppButton>
          </div>
        </div>

        <AppButton
          className="mb-3 w-full justify-start rounded-xl"
          disabled={isMutating}
          onClick={() => void handleCreateConversation()}
          type="button"
        >
          <MessageSquarePlus className="h-4 w-4" />
          New conversation
        </AppButton>

        <div className="mb-3 grid grid-cols-1 gap-2">
          <AppButton
            className={navButtonClassName}
            onClick={() => {
              navigate("/app/chat");
              onConversationSelect?.();
            }}
            size="sm"
            type="button"
            variant={isChatRoute ? "primary" : "secondary"}
          >
            <MessagesSquare className="h-4 w-4" />
            Chat
          </AppButton>
          <AppButton
            className={navButtonClassName}
            onClick={() => {
              navigate("/app/settings/rules");
              onConversationSelect?.();
            }}
            size="sm"
            type="button"
            variant={isRulesRoute ? "primary" : "secondary"}
          >
            <Scale className="h-4 w-4" />
            Rules
          </AppButton>
          <AppButton
            className={navButtonClassName}
            onClick={() => {
              navigate("/app/settings/system-prompt");
              onConversationSelect?.();
            }}
            size="sm"
            type="button"
            variant={isSystemPromptRoute ? "primary" : "secondary"}
          >
            <SlidersHorizontal className="h-4 w-4" />
            System Prompt
          </AppButton>
          <AppButton
            className={navButtonClassName}
            onClick={() => {
              navigate("/app/suggestions");
              onConversationSelect?.();
            }}
            size="sm"
            type="button"
            variant={isSuggestionsRoute ? "primary" : "secondary"}
          >
            <WandSparkles className="h-4 w-4" />
            Suggestions
          </AppButton>
        </div>

        <div className="min-h-0 flex-1 overflow-hidden rounded-2xl border border-border/70 bg-background shadow-app-sm">
          <div className="border-b border-border/70 px-4 py-3">
            <p className="text-sm font-semibold">Conversations</p>
            <p className="text-xs text-muted-foreground">Recent chat threads and workspace history.</p>
          </div>

          <ScrollArea className="h-full">
            <div className="space-y-2 p-3 pb-6">
              {conversationsQuery.isLoading && (
                <AppLoadingState
                  compact
                  description="Loading recent chat threads."
                  title="Loading conversations"
                />
              )}

              {conversationsQuery.isError && (
                <AppAlert
                  description="Failed to load conversations."
                  title="Conversation list unavailable"
                  variant="error"
                />
              )}

              {!conversationsQuery.isLoading &&
                !conversationsQuery.isError &&
                conversations.length === 0 && (
                  <EmptyState
                    description="Create a new conversation to start chatting."
                    title="No conversations yet"
                  />
                )}

              {conversations.map((item) => (
                <ConversationListItem
                  isActive={activeConversationId === item.id}
                  item={item}
                  key={item.id}
                  onDelete={setConversationPendingDelete}
                  onOpen={handleOpenConversation}
                  onRename={startRenameConversation}
                />
              ))}
            </div>
          </ScrollArea>
        </div>
      </aside>

      <AppModal
        description="Choose a clear title so this thread is easier to find later."
        footer={
          <div className="flex justify-end gap-2">
            <AppButton onClick={cancelRenameConversation} type="button" variant="secondary">
              Cancel
            </AppButton>
            <AppButton
              disabled={
                updateConversationMutation.isPending ||
                !renameDraft.trim() ||
                renameDraft.trim().length > conversationTitleMaxLength
              }
              onClick={() => void submitRenameConversation()}
              type="button"
            >
              {updateConversationMutation.isPending ? "Saving..." : "Save changes"}
            </AppButton>
          </div>
        }
        onClose={cancelRenameConversation}
        open={Boolean(renamingConversation)}
        size="sm"
        title="Rename conversation"
      >
        <div className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="conversation-rename-input" required>
              Conversation name
            </Label>
          <Input
            autoFocus
            id="conversation-rename-input"
            maxLength={conversationTitleMaxLength}
            onChange={(event) => updateRenameDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void submitRenameConversation();
              }
            }}
            placeholder="Conversation name"
            value={renameDraft}
          />
            <FieldHelpText>Use a short, recognizable title so the thread is easier to find later.</FieldHelpText>
          </div>
          <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
            <span>{renameDraft.trim().length}/{conversationTitleMaxLength}</span>
            {renamingConversation && (
              <span className="truncate">Current: {renamingConversation.title?.trim() || "Untitled conversation"}</span>
            )}
          </div>
          {renameError ? <InlineErrorText>{renameError}</InlineErrorText> : null}
        </div>
      </AppModal>

      <ConfirmDialog
        confirmLabel={deleteConversationMutation.isPending ? "Deleting..." : "Delete conversation"}
        confirmVariant="danger"
        description={
          conversationPendingDelete
            ? `Delete "${conversationPendingDelete.title?.trim() || "Untitled conversation"}"? This cannot be undone.`
            : undefined
        }
        isBusy={deleteConversationMutation.isPending}
        onClose={() => setConversationPendingDelete(null)}
        onConfirm={() => {
          void handleDeleteConversation();
        }}
        open={Boolean(conversationPendingDelete)}
        title="Delete conversation?"
      />
    </>
  );
}
