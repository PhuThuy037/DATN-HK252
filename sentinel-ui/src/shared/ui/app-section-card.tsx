import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/shared/lib/utils";
import { Card } from "@/shared/ui/card";

type AppSectionCardProps = Omit<HTMLAttributes<HTMLDivElement>, "title"> & {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  headerClassName?: string;
  contentClassName?: string;
};

export function AppSectionCard({
  title,
  description,
  actions,
  className,
  children,
  headerClassName,
  contentClassName,
  ...props
}: AppSectionCardProps) {
  return (
    <Card className={cn("space-y-4 p-4 md:p-5", className)} {...props}>
      {(title || description || actions) && (
        <div className={cn("flex flex-col gap-3 md:flex-row md:items-start md:justify-between", headerClassName)}>
          <div className="space-y-1">
            {title ? <h2 className="text-heading font-semibold text-foreground">{title}</h2> : null}
            {description ? <p className="text-label text-muted-foreground">{description}</p> : null}
          </div>
          {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
        </div>
      )}
      <div className={cn("space-y-3", contentClassName)}>{children}</div>
    </Card>
  );
}
