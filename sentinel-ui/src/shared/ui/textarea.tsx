import * as React from "react";
import { cn } from "@/shared/lib/utils";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => {
  return (
    <textarea
      className={cn(
        "min-h-20 w-full rounded-md border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring",
        className
      )}
      ref={ref}
      {...props}
    />
  );
});

Textarea.displayName = "Textarea";
