import * as React from "react";
import { cn } from "@/shared/lib/utils";

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "outline" | "ghost";
  size?: "default" | "sm" | "lg" | "icon";
};

const variantClasses: Record<NonNullable<ButtonProps["variant"]>, string> = {
  default: "bg-primary text-primary-foreground hover:opacity-90",
  outline: "border bg-background hover:bg-accent",
  ghost: "hover:bg-accent",
};

const sizeClasses: Record<NonNullable<ButtonProps["size"]>, string> = {
  default: "h-10 px-4 py-2",
  sm: "h-8 rounded-md px-3 text-xs",
  lg: "h-11 rounded-md px-8",
  icon: "h-9 w-9",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", ...props }, ref) => {
    return (
      <button
        className={cn(
          "inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
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
