import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  EllipsisVertical,
  LogOut,
  MessageSquarePlus,
  MessageSquareText,
  Pencil,
  Settings,
  Trash2,
} from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { useConversations } from "@/features/conversations/hooks/useConversations";
import {
  extractAuthErrorMessage,
  logout,
} from "@/features/auth/api/authApi";
import { useAuthStore } from "@/features/auth/store/authStore";
import { cn } from "@/shared/lib/utils";
import {
  createConversation,
  deleteConversation,
  updateConversation,
} from "@/shared/api/conversationsApi";
import { AppLoadingState } from "@/shared/ui/app-loading-state";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";
import { EmptyState } from "@/shared/ui/empty-state";
import { Input } from "@/shared/ui/input";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { toast } from "@/shared/ui/use-toast";
import type { ConversationListItem } from "@/shared/types";

function formatUpdatedAt(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

type ConversationItemProps = {
  item: ConversationListItem;
  isActive: boolean;
  isProcessing: boolean;
  editingTitle?: string;
  isEditing: boolean;
  onDraftTitleChange: (value: string) => void;
  onRenameSubmit: () => void;
  onRenameCancel: () => void;
  menuOpen: boolean;
  onMenuToggle: () => void;
  onRenameStart: () => void;
  onArchive: () => void;
  onDelete: () => void;
  onClick: (conversationId: string) => void;
};

function ConversationItem({
  item,
  isActive,
  isProcessing,
  editingTitle,
  isEditing,
  onDraftTitleChange,
  onRenameSubmit,
  onRenameCancel,
  menuOpen,
  onMenuToggle,
  onRenameStart,
  onArchive,
  onDelete,
  onClick,
}: ConversationItemProps) {
  return (
    <div
      className={cn(
        "rounded-md border p-2 transition-colors",
        isActive && "border-primary bg-accent"
      )}
    >
      <div className="flex items-start gap-2">
        <button
          className="min-w-0 flex-1 rounded-md px-2 py-1 text-left hover:bg-accent/70"
          onClick={() => onClick(item.id)}
          type="button"
        >
          <div className="truncate text-sm font-medium">
            {item.title || "Untitled conversation"}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {formatUpdatedAt(item.updated_at)}
          </div>
        </button>

        <div className="relative">
          <Button
            className="h-8 w-8 p-0"
            disabled={isProcessing}
            onClick={onMenuToggle}
            size="sm"
            type="button"
            variant="ghost"
          >
            <EllipsisVertical className="h-4 w-4" />
          </Button>

          {menuOpen && (
            <div className="absolute right-0 top-9 z-20 w-36 rounded-md border bg-background p-1 shadow-md">
              <button
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs hover:bg-accent"
                disabled={isProcessing}
                onClick={onRenameStart}
                type="button"
              >
                <Pencil className="h-3.5 w-3.5" />
                Rename
              </button>
              <button
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs hover:bg-accent"
                disabled={isProcessing}
                onClick={onArchive}
                type="button"
              >
                <Archive className="h-3.5 w-3.5" />
                Archive
              </button>
              <button
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-destructive hover:bg-destructive/10"
                disabled={isProcessing}
                onClick={onDelete}
                type="button"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Delete
              </button>
            </div>
          )}
        </div>
      </div>

      {isEditing && (
        <div className="mt-2 space-y-2 border-t pt-2">
          <Input
            onChange={(event) => onDraftTitleChange(event.target.value)}
            placeholder="Conversation title"
            value={editingTitle ?? ""}
          />
          <div className="flex justify-end gap-2">
            <Button onClick={onRenameCancel} size="sm" type="button" variant="ghost">
              Cancel
            </Button>
            <Button
              disabled={isProcessing || !editingTitle?.trim()}
              onClick={onRenameSubmit}
              size="sm"
              type="button"
            >
              Save
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

type SidebarProps = {
  className?: string;
  onConversationSelect?: () => void;
};

export function Sidebar({ className, onConversationSelect }: SidebarProps) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { conversationId } = useParams();
  const user = useAuthStore((state) => state.user);
  const refreshToken = useAuthStore((state) => state.refreshToken);
  const clearAuth = useAuthStore((state) => state.clearAuth);
  const { data, isLoading, isError } = useConversations();
  const conversations = data?.items ?? [];
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [editingConversationId, setEditingConversationId] = useState<string | null>(
    null
  );
  const [draftTitle, setDraftTitle] = useState("");
  const [openMenuConversationId, setOpenMenuConversationId] = useState<string | null>(
    null
  );
  const [pendingDeleteConversationId, setPendingDeleteConversationId] = useState<string | null>(
    null
  );
  const containerRef = useRef<HTMLDivElement | null>(null);

  const processingConversationId = useRef<string | null>(null);

  const invalidateConversationQueries = () => {
    queryClient.invalidateQueries({ queryKey: ["conversations"] });
  };

  const createConversationMutation = useMutation({
    mutationFn: () => createConversation({ title: "New conversation" }),
    onSuccess: (conversation) => {
      invalidateConversationQueries();
      navigate(`/app/chat/${conversation.id}`);
      onConversationSelect?.();
      toast({
        title: "Conversation created",
        description: "A new chat workspace is ready.",
        variant: "success",
      });
    },
    onError: () => {
      toast({
        title: "Create failed",
        description: "Unable to create conversation.",
        variant: "destructive",
      });
    },
  });

  const updateConversationMutation = useMutation({
    mutationFn: (payload: {
      conversationId: string;
      title?: string | null;
      status?: "active" | "archived";
    }) =>
      updateConversation(payload.conversationId, {
        title: payload.title,
        status: payload.status,
      }),
    onMutate: ({ conversationId: targetConversationId }) => {
      processingConversationId.current = targetConversationId;
    },
    onSuccess: (_, payload) => {
      invalidateConversationQueries();
      if (payload.status === "archived") {
        toast({
          title: "Conversation archived",
          description: "It has been removed from active history.",
          variant: "success",
        });
      } else {
        toast({
          title: "Conversation updated",
          description: "Conversation metadata has been updated.",
          variant: "success",
        });
      }
    },
    onError: () => {
      toast({
        title: "Update failed",
        description: "Unable to update conversation.",
        variant: "destructive",
      });
    },
    onSettled: () => {
      processingConversationId.current = null;
    },
  });

  const deleteConversationMutation = useMutation({
    mutationFn: (targetConversationId: string) => deleteConversation(targetConversationId),
    onMutate: (targetConversationId) => {
      processingConversationId.current = targetConversationId;
    },
    onSuccess: (_data, targetConversationId) => {
      invalidateConversationQueries();
      if (conversationId === targetConversationId) {
        navigate("/app/chat");
      }
      toast({
        title: "Conversation deleted",
        description: "Conversation has been removed from history.",
        variant: "success",
      });
    },
    onError: () => {
      toast({
        title: "Delete failed",
        description: "Unable to delete conversation.",
        variant: "destructive",
      });
    },
    onSettled: () => {
      processingConversationId.current = null;
    },
  });

  const isAnyMutationPending =
    createConversationMutation.isPending ||
    updateConversationMutation.isPending ||
    deleteConversationMutation.isPending;

  const hasConversations = conversations.length > 0;

  useEffect(() => {
    const onMouseDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpenMenuConversationId(null);
      }
    };

    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, []);

  const handleConversationClick = (conversationId: string) => {
    navigate(`/app/chat/${conversationId}`);
    onConversationSelect?.();
    setOpenMenuConversationId(null);
  };

  const handleCreateConversation = async () => {
    try {
      await createConversationMutation.mutateAsync();
    } catch {
      // Handled by mutation callbacks.
    }
  };

  const startRename = (item: ConversationListItem) => {
    setEditingConversationId(item.id);
    setDraftTitle(item.title ?? "");
    setOpenMenuConversationId(null);
  };

  const submitRename = async () => {
    if (!editingConversationId || !draftTitle.trim()) {
      return;
    }

    try {
      await updateConversationMutation.mutateAsync({
        conversationId: editingConversationId,
        title: draftTitle.trim(),
      });
      setEditingConversationId(null);
      setDraftTitle("");
    } catch {
      // Handled by mutation callbacks.
    }
  };

  const archiveConversation = async (targetConversationId: string) => {
    setOpenMenuConversationId(null);
    try {
      await updateConversationMutation.mutateAsync({
        conversationId: targetConversationId,
        status: "archived",
      });
      if (conversationId === targetConversationId) {
        navigate("/app/chat");
        onConversationSelect?.();
      }
    } catch {
      // Handled by mutation callbacks.
    }
  };

  const removeConversation = async (targetConversationId: string) => {
    setOpenMenuConversationId(null);
    try {
      await deleteConversationMutation.mutateAsync(targetConversationId);
      setPendingDeleteConversationId(null);
    } catch {
      // Handled by mutation callbacks.
    }
  };

  const sortedConversations = useMemo(
    () =>
      [...conversations].sort(
        (a, b) =>
          new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      ),
    [conversations]
  );

  const handleLogout = async () => {
    setIsLoggingOut(true);

    try {
      if (refreshToken) {
        await logout({ refresh_token: refreshToken });
      }
      toast({
        title: "Logged out",
        description: "Your session has ended.",
        variant: "success",
      });
    } catch (error) {
      toast({
        title: "Logout warning",
        description: extractAuthErrorMessage(error),
        variant: "destructive",
      });
    } finally {
      clearAuth();
      queryClient.clear();
      navigate("/login");
      onConversationSelect?.();
      setIsLoggingOut(false);
    }
  };

  return (
    <aside className={cn("flex h-full flex-col border-r bg-muted/40 p-4", className)}>
      <div className="mb-4 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h1 className="text-lg font-semibold">Sentinel Workspace</h1>
            <p className="text-xs text-muted-foreground">
              Conversation history sidebar
            </p>
          </div>
          <Button
            className="h-8 px-2"
            disabled={isLoggingOut}
            onClick={() => void handleLogout()}
            size="sm"
            type="button"
            variant="outline"
          >
            <LogOut className="mr-1 h-3.5 w-3.5" />
            {isLoggingOut ? "..." : "Logout"}
          </Button>
        </div>
        {user?.email && (
          <p className="truncate text-xs text-muted-foreground">{user.email}</p>
        )}
      </div>

      <Button
        className="mb-3 w-full justify-start gap-2"
        disabled={isAnyMutationPending}
        onClick={handleCreateConversation}
        type="button"
      >
        <MessageSquarePlus className="h-4 w-4" />
        New conversation
      </Button>

      <nav className="mb-3 space-y-1 text-sm">
        <button
          className={cn(
            "flex w-full items-center gap-2 rounded-md px-3 py-2 hover:bg-accent",
            !conversationId && "bg-accent"
          )}
          onClick={() => {
            navigate("/app/chat");
            onConversationSelect?.();
          }}
          type="button"
        >
          <MessageSquareText className="h-4 w-4" />
          Chat home
        </button>
        <button
          className="flex w-full items-center gap-2 rounded-md px-3 py-2 hover:bg-accent"
          onClick={() => {
            navigate("/app/settings/system-prompt");
            onConversationSelect?.();
          }}
          type="button"
        >
          <Settings className="h-4 w-4" />
          System Prompt
        </button>
      </nav>

      <Card className="min-h-0 flex-1 bg-background p-2">
        <ScrollArea className="h-full px-1" ref={containerRef}>
          <div className="space-y-2 py-1">
            {isLoading && (
              <AppLoadingState
                compact
                description="Loading recent conversations."
                title="Loading conversations"
              />
            )}
            {isError && (
              <p className="p-2 text-xs text-destructive">
                Failed to load conversations.
              </p>
            )}
            {!isLoading && !isError && !hasConversations && (
              <EmptyState
                description="Create your first chat to begin scanning."
                title="No conversations yet"
              />
            )}
            {sortedConversations.map((conversation) => (
              <ConversationItem
                editingTitle={editingConversationId === conversation.id ? draftTitle : ""}
                isActive={conversation.id === conversationId}
                isEditing={editingConversationId === conversation.id}
                isProcessing={
                  isAnyMutationPending &&
                  processingConversationId.current === conversation.id
                }
                item={conversation}
                key={conversation.id}
                menuOpen={openMenuConversationId === conversation.id}
                onArchive={() => void archiveConversation(conversation.id)}
                onClick={handleConversationClick}
                onDelete={() => setPendingDeleteConversationId(conversation.id)}
                onDraftTitleChange={setDraftTitle}
                onMenuToggle={() =>
                  setOpenMenuConversationId((current) =>
                    current === conversation.id ? null : conversation.id
                  )
                }
                onRenameCancel={() => {
                  setEditingConversationId(null);
                  setDraftTitle("");
                }}
                onRenameStart={() => startRename(conversation)}
                onRenameSubmit={() => void submitRename()}
              />
            ))}
          </div>
        </ScrollArea>
      </Card>

      <ConfirmDialog
        confirmLabel={deleteConversationMutation.isPending ? "Deleting..." : "Delete conversation"}
        confirmVariant="danger"
        description="Delete this conversation? This action cannot be undone."
        isBusy={deleteConversationMutation.isPending}
        onClose={() => setPendingDeleteConversationId(null)}
        onConfirm={() => {
          if (pendingDeleteConversationId) {
            void removeConversation(pendingDeleteConversationId);
          }
        }}
        open={Boolean(pendingDeleteConversationId)}
        title="Delete conversation?"
      />
    </aside>
  );
}
