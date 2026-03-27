import type { HTMLAttributes, ReactNode } from "react";
import { AlertCircle, AlertTriangle, CheckCircle2, Info } from "lucide-react";
import { cn } from "@/shared/lib/utils";

type AppAlertVariant = "info" | "success" | "warning" | "error";

type AppAlertProps = Omit<HTMLAttributes<HTMLDivElement>, "title"> & {
  variant?: AppAlertVariant;
  title?: ReactNode;
  description?: ReactNode;
  icon?: ReactNode;
};

const variantClasses: Record<AppAlertVariant, string> = {
  info: "border-primary/20 bg-primary/5 text-foreground",
  success: "border-success-border bg-success-muted text-foreground",
  warning: "border-warning-border bg-warning-muted text-foreground",
  error: "border-danger-border bg-danger-muted text-foreground",
};

const defaultIcons: Record<AppAlertVariant, ReactNode> = {
  info: <Info className="mt-0.5 h-4 w-4 text-primary" />,
  success: <CheckCircle2 className="mt-0.5 h-4 w-4 text-success" />,
  warning: <AlertTriangle className="mt-0.5 h-4 w-4 text-warning" />,
  error: <AlertCircle className="mt-0.5 h-4 w-4 text-danger" />,
};

export function AppAlert({
  variant = "info",
  title,
  description,
  icon,
  className,
  children,
  ...props
}: AppAlertProps) {
  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-xl border px-4 py-3 text-sm",
        variantClasses[variant],
        className
      )}
      role={variant === "error" ? "alert" : "status"}
      {...props}
    >
      <div className="shrink-0">{icon ?? defaultIcons[variant]}</div>
      <div className="min-w-0 space-y-1">
        {title ? <p className="font-semibold text-foreground">{title}</p> : null}
        {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
        {children}
      </div>
    </div>
  );
}
