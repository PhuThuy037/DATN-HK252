import type { HTMLAttributes, ReactNode } from "react";
import { Inbox } from "lucide-react";
import { cn } from "@/shared/lib/utils";

type EmptyStateProps = Omit<HTMLAttributes<HTMLDivElement>, "title"> & {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
};

export function EmptyState({
  title,
  description,
  action,
  icon,
  className,
  ...props
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-dashed border-border/90 bg-muted/10 px-6 py-8 text-center",
        className
      )}
      {...props}
    >
      <div className="mb-3 rounded-full bg-background p-3 text-muted-foreground shadow-app-sm">
        {icon ?? <Inbox className="h-5 w-5" />}
      </div>
      <p className="text-sm font-semibold text-foreground">{title}</p>
      {description ? (
        <p className="mt-1 max-w-md text-xs leading-5 text-muted-foreground">{description}</p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
