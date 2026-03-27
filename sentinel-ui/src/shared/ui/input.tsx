import * as React from "react";
import { cn } from "@/shared/lib/utils";
import { appControlClassName } from "@/shared/ui/design-tokens";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={cn(
          appControlClassName,
          className
        )}
        {...props}
      />
    );
  }
);

Input.displayName = "Input";
