import type { ReactNode } from "react";
import { cn } from "@/shared/lib/utils";

type AppPageHeaderProps = {
  title: ReactNode;
  subtitle?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
  className?: string;
};

export function AppPageHeader({
  title,
  subtitle,
  meta,
  actions,
  className,
}: AppPageHeaderProps) {
  return (
    <header
      className={cn(
        "flex flex-col gap-3 md:flex-row md:items-start md:justify-between",
        className
      )}
    >
      <div className="space-y-1">
        <h1 className="text-title font-semibold tracking-tight text-foreground">{title}</h1>
        {subtitle ? <p className="text-body text-muted-foreground">{subtitle}</p> : null}
        {meta ? <div className="text-caption text-muted-foreground">{meta}</div> : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}
