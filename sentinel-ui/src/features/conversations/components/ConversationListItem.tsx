import { useEffect, useRef, useState } from "react";
import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { AppButton } from "@/shared/ui/app-button";
import type { ConversationListItem as ConversationListItemType } from "@/shared/types";

type ConversationListItemProps = {
  item: ConversationListItemType;
  isActive: boolean;
  onOpen: (conversationId: string) => void;
  onRename: (item: ConversationListItemType) => void;
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

function getPreviewText(item: ConversationListItemType) {
  const preview = item.last_message_preview?.trim();
  if (preview) {
    return preview;
  }
  return "Open the conversation to continue the thread.";
}

export function ConversationListItem({
  item,
  isActive,
  onOpen,
  onRename,
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
        "group relative rounded-2xl border transition-all duration-150",
        isActive
          ? "border-primary/35 bg-primary/10 shadow-app-sm"
          : "border-transparent bg-background/70 hover:-translate-y-px hover:border-border/80 hover:bg-background hover:shadow-app-sm"
      )}
    >
      <button
        className="block w-full rounded-2xl px-4 py-3 text-left"
        onClick={() => onOpen(item.id)}
        type="button"
      >
        <div className="pr-10">
          <div className="flex items-start justify-between gap-3">
            <p className="truncate text-sm font-semibold leading-5 text-foreground">
              {item.title?.trim() || "Untitled conversation"}
            </p>
            <span className="shrink-0 text-[11px] text-muted-foreground">
              {formatDateTime(item.updated_at)}
            </span>
          </div>

          <p className="mt-1 max-h-10 overflow-hidden text-xs leading-5 text-muted-foreground">
            {getPreviewText(item)}
          </p>
        </div>
      </button>

      <div className="absolute right-3 top-3" ref={menuRef}>
        <AppButton
          aria-expanded={isMenuOpen}
          aria-haspopup="menu"
          aria-label="Open conversation actions"
          className={cn(
            "h-8 w-8 rounded-full px-0 transition-opacity",
            "opacity-0 group-hover:opacity-100",
            (isActive || isMenuOpen) && "opacity-100"
          )}
          onClick={(event) => {
            event.stopPropagation();
            setIsMenuOpen((prev) => !prev);
          }}
          size="icon"
          type="button"
          variant="secondary"
        >
          <MoreHorizontal className="h-4 w-4" />
        </AppButton>

        {isMenuOpen && (
          <div
            className="absolute right-0 top-10 z-20 min-w-[150px] rounded-xl border border-border/80 bg-background p-1.5 shadow-app-md"
            role="menu"
          >
            <button
              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs text-foreground transition-colors hover:bg-muted"
              onClick={(event) => {
                event.stopPropagation();
                setIsMenuOpen(false);
                onRename(item);
              }}
              role="menuitem"
              type="button"
            >
              <Pencil className="h-3.5 w-3.5" />
              Rename
            </button>
            <button
              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs text-danger transition-colors hover:bg-danger-muted"
              onClick={(event) => {
                event.stopPropagation();
                setIsMenuOpen(false);
                onDelete(item);
              }}
              role="menuitem"
              type="button"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
