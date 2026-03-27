import type { HTMLAttributes } from "react";
import { cn } from "@/shared/lib/utils";
import { appInlineErrorTextClassName } from "@/shared/ui/design-tokens";

export function InlineErrorText({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      aria-live="polite"
      className={cn(appInlineErrorTextClassName, className)}
      role="alert"
      {...props}
    />
  );
}
