import * as React from "react";
import { cn } from "@/shared/lib/utils";

export const Label = React.forwardRef<
  HTMLLabelElement,
  React.LabelHTMLAttributes<HTMLLabelElement>
>(({ className, ...props }, ref) => {
  return (
    <label
      className={cn("text-sm font-medium leading-none", className)}
      ref={ref}
      {...props}
    />
  );
});

Label.displayName = "Label";
