import { useEffect, useRef, useState } from "react";
import { Archive, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import type { ConversationListItem as ConversationListItemType } from "@/shared/types";

type ConversationListItemProps = {
  item: ConversationListItemType;
  isActive: boolean;
  isRenaming: boolean;
  isRenameSubmitting?: boolean;
  renameError?: string | null;
  renameValue: string;
  onOpen: (conversationId: string) => void;
  onRenameChange: (value: string) => void;
  onRenameCancel: () => void;
  onRenameStart: (item: ConversationListItemType) => void;
  onRenameSubmit: () => void;
  onArchive: (item: ConversationListItemType) => void;
  onDelete: (item: ConversationListItemType) => void;
};

function formatDateTime(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ConversationListItem({
  item,
  isActive,
  isRenaming,
  isRenameSubmitting = false,
  renameError,
  renameValue,
  onOpen,
  onRenameChange,
  onRenameCancel,
  onRenameStart,
  onRenameSubmit,
  onArchive,
  onDelete,
}: ConversationListItemProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const handleOutsideClick = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) {
        setIsMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, []);

  return (
    <div
      className={cn(
        "group rounded-xl border p-2.5 transition-colors",
        isActive
          ? "border-primary/60 bg-primary/10 shadow-sm"
          : "border-border/70 bg-background hover:border-border hover:bg-muted/50"
      )}
    >
      <div className="flex items-start gap-1">
        {isRenaming ? (
          <div className="min-w-0 flex-1 rounded-lg border bg-background px-2 py-2">
            <Input
              autoFocus
              className="h-8 text-sm"
              maxLength={300}
              onChange={(event) => onRenameChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  onRenameSubmit();
                }
                if (event.key === "Escape") {
                  event.preventDefault();
                  onRenameCancel();
                }
              }}
              placeholder="Conversation name"
              value={renameValue}
            />
            {renameError && <p className="mt-1 text-xs text-destructive">{renameError}</p>}
            <div className="mt-2 flex justify-end gap-1">
              <Button
                disabled={isRenameSubmitting}
                onClick={onRenameCancel}
                size="sm"
                type="button"
                variant="ghost"
              >
                Cancel
              </Button>
              <Button
                disabled={
                  isRenameSubmitting ||
                  !renameValue.trim() ||
                  renameValue.trim().length > 300
                }
                onClick={onRenameSubmit}
                size="sm"
                type="button"
              >
                {isRenameSubmitting ? "Saving..." : "Save"}
              </Button>
            </div>
          </div>
        ) : (
          <button
            className="min-w-0 flex-1 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-accent/70"
            onClick={() => onOpen(item.id)}
            type="button"
          >
            <p className="truncate text-sm font-medium leading-5">
              {item.title?.trim() || "Untitled conversation"}
            </p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              {formatDateTime(item.updated_at)}
            </p>
          </button>
        )}

        {!isRenaming && (
          <div className="relative" ref={menuRef}>
            <Button
              aria-expanded={isMenuOpen}
              aria-haspopup="menu"
              aria-label="Open conversation actions"
              className={cn(
                "h-7 w-7 transition-opacity",
                "opacity-0 group-hover:opacity-100",
                (isActive || isMenuOpen) && "opacity-100"
              )}
              onClick={(event) => {
                event.stopPropagation();
                setIsMenuOpen((prev) => !prev);
              }}
              size="icon"
              type="button"
              variant="ghost"
            >
              <MoreHorizontal className="h-4 w-4" />
            </Button>

            {isMenuOpen && (
              <div className="absolute right-0 top-8 z-20 min-w-[150px] rounded-md border bg-background p-1 shadow-lg">
                <button
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs hover:bg-accent"
                  onClick={(event) => {
                    event.stopPropagation();
                    setIsMenuOpen(false);
                    onRenameStart(item);
                  }}
                  type="button"
                >
                  <Pencil className="h-3.5 w-3.5" />
                  Rename
                </button>
                <button
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs hover:bg-accent"
                  onClick={(event) => {
                    event.stopPropagation();
                    setIsMenuOpen(false);
                    onArchive(item);
                  }}
                  type="button"
                >
                  <Archive className="h-3.5 w-3.5" />
                  Archive
                </button>
                <button
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-destructive hover:bg-destructive/10"
                  onClick={(event) => {
                    event.stopPropagation();
                    setIsMenuOpen(false);
                    onDelete(item);
                  }}
                  type="button"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
