import * as React from "react";
import { cn } from "@/shared/lib/utils";
import { appFieldLabelClassName } from "@/shared/ui/design-tokens";

export const Label = React.forwardRef<
  HTMLLabelElement,
  React.LabelHTMLAttributes<HTMLLabelElement> & {
    required?: boolean;
  }
>(({ className, children, required = false, ...props }, ref) => {
  return (
    <label
      className={cn(appFieldLabelClassName, "leading-none", className)}
      ref={ref}
      {...props}
    >
      {children}
      {required ? <span className="ml-1 text-danger">*</span> : null}
    </label>
  );
});

Label.displayName = "Label";
