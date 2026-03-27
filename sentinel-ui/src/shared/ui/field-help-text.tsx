import type { HTMLAttributes } from "react";
import { cn } from "@/shared/lib/utils";
import { appFieldHelpTextClassName } from "@/shared/ui/design-tokens";

export function FieldHelpText({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn(appFieldHelpTextClassName, className)} {...props} />;
}
