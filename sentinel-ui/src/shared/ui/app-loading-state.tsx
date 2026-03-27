import type { HTMLAttributes, ReactNode } from "react";
import { LoaderCircle } from "lucide-react";
import { cn } from "@/shared/lib/utils";

type AppLoadingStateProps = Omit<HTMLAttributes<HTMLDivElement>, "title"> & {
  title?: ReactNode;
  description?: ReactNode;
  compact?: boolean;
};

export function AppLoadingState({
  title = "Loading",
  description = "Please wait while we prepare this view.",
  compact = false,
  className,
  ...props
}: AppLoadingStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-border/80 bg-muted/20 text-center",
        compact ? "px-5 py-6" : "px-6 py-10",
        className
      )}
      role="status"
      {...props}
    >
      <div className="mb-3 rounded-full bg-background p-3 text-primary shadow-app-sm">
        <LoaderCircle className="h-5 w-5 animate-spin" />
      </div>
      <p className="text-sm font-semibold text-foreground">{title}</p>
      {description ? (
        <p className="mt-1 max-w-md text-xs leading-5 text-muted-foreground">
          {description}
        </p>
      ) : null}
    </div>
  );
}
