import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { AppButton } from "@/shared/ui/app-button";
import { appModalPanelClassName } from "@/shared/ui/design-tokens";

type AppModalProps = {
  open: boolean;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  bodyClassName?: string;
  onClose: () => void;
  closeOnOverlayClick?: boolean;
  closeOnEscape?: boolean;
  size?: "sm" | "md" | "lg" | "xl";
};

const sizeClasses: Record<NonNullable<AppModalProps["size"]>, string> = {
  sm: "max-w-md",
  md: "max-w-xl",
  lg: "max-w-3xl",
  xl: "max-w-5xl",
};

export function AppModal({
  open,
  title,
  description,
  children,
  footer,
  bodyClassName,
  onClose,
  closeOnOverlayClick = true,
  closeOnEscape = true,
  size = "md",
}: AppModalProps) {
  useEffect(() => {
    if (!open) {
      return undefined;
    }

    const originalOverflow = document.body.style.overflow;
    const handleEscape = (event: KeyboardEvent) => {
      if (closeOnEscape && event.key === "Escape") {
        onClose();
      }
    };

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleEscape);
    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener("keydown", handleEscape);
    };
  }, [closeOnEscape, onClose, open]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4"
      onClick={() => {
        if (closeOnOverlayClick) {
          onClose();
        }
      }}
      role="presentation"
    >
      <div
        aria-modal="true"
        className={cn(
          appModalPanelClassName,
          "flex max-h-[calc(100vh-2rem)] w-full flex-col overflow-hidden",
          sizeClasses[size]
        )}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-border/70 px-5 py-4">
          <div className="space-y-1">
            <h3 className="text-heading font-semibold text-foreground">{title}</h3>
            {description ? <p className="text-label text-muted-foreground">{description}</p> : null}
          </div>
          <AppButton
            aria-label="Close modal"
            className="shrink-0"
            onClick={onClose}
            size="icon"
            type="button"
            variant="secondary"
          >
            <X className="h-4 w-4" />
          </AppButton>
        </div>
        <div
          className={cn(
            "min-h-0 flex-1 overflow-y-auto overscroll-contain scroll-auto px-5 py-4 [contain:layout_paint] [scrollbar-gutter:stable]",
            bodyClassName
          )}
          style={{ WebkitOverflowScrolling: "touch" }}
        >
          {children}
        </div>
        {footer ? <div className="shrink-0 border-t border-border/70 px-5 py-4">{footer}</div> : null}
      </div>
    </div>
  );
}
