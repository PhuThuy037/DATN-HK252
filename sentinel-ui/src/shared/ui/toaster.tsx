import { cn } from "@/shared/lib/utils";
import { useToastStore } from "@/shared/ui/use-toast";

function toastVariantClass(variant?: string) {
  if (variant === "destructive") {
    return "border-destructive/40 bg-destructive text-destructive-foreground";
  }
  if (variant === "success") {
    return "border-green-300 bg-green-50 text-green-900";
  }
  return "border bg-background";
}

export function Toaster() {
  const toasts = useToastStore((state) => state.toasts);
  const dismiss = useToastStore((state) => state.dismiss);

  return (
    <div className="pointer-events-none fixed left-1/2 top-4 z-[100] flex w-[420px] max-w-[95vw] -translate-x-1/2 flex-col gap-2">
      {toasts.map((item) => (
        <div
          className={cn(
            "pointer-events-auto rounded-md border p-3 shadow-md",
            toastVariantClass(item.variant)
          )}
          key={item.id}
          role="status"
        >
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-sm font-semibold">{item.title}</p>
              {item.description && (
                <p className="mt-1 text-xs opacity-90">{item.description}</p>
              )}
            </div>
            <button
              aria-label="Close toast"
              className="text-xs opacity-70 hover:opacity-100"
              onClick={() => dismiss(item.id)}
              type="button"
            >
              Close
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
