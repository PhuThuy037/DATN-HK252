import * as React from "react";
import { cn } from "@/shared/lib/utils";

export function Badge({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "app-badge-base",
        className
      )}
      {...props}
    />
  );
}
