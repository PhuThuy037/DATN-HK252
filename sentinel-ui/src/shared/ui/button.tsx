import * as React from "react";
import { cn } from "@/shared/lib/utils";

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "secondary" | "outline" | "ghost" | "destructive";
  size?: "default" | "sm" | "lg" | "icon";
};

const variantClasses: Record<NonNullable<ButtonProps["variant"]>, string> = {
  default: "border border-transparent bg-primary text-primary-foreground shadow-app-sm hover:bg-primary/90",
  secondary: "border border-border/80 bg-background text-foreground shadow-app-sm hover:bg-muted/80",
  outline: "border border-border/80 bg-background text-foreground hover:bg-accent/70",
  ghost: "border border-transparent text-muted-foreground hover:bg-accent/70 hover:text-foreground",
  destructive: "border border-transparent bg-danger text-danger-foreground shadow-app-sm hover:bg-danger/90",
};

const sizeClasses: Record<NonNullable<ButtonProps["size"]>, string> = {
  default: "h-10 px-4 py-2",
  sm: "h-9 rounded-lg px-3 text-xs",
  lg: "h-11 rounded-lg px-5",
  icon: "h-10 w-10",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", ...props }, ref) => {
    return (
      <button
        className={cn(
          "inline-flex items-center justify-center gap-2 rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
          variantClasses[variant],
          sizeClasses[size],
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);

Button.displayName = "Button";
