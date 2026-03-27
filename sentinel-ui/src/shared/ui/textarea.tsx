import * as React from "react";
import { cn } from "@/shared/lib/utils";
import { appControlClassName } from "@/shared/ui/design-tokens";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => {
  return (
    <textarea
      className={cn(
        appControlClassName,
        "min-h-20 h-auto resize-y py-3 leading-6",
        className
      )}
      ref={ref}
      {...props}
    />
  );
});

Textarea.displayName = "Textarea";
