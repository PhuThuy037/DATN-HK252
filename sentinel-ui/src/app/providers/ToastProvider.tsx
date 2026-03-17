import { PropsWithChildren } from "react";
import { Toaster } from "@/shared/ui/toaster";

export function AppToastProvider({ children }: PropsWithChildren) {
  return (
    <>
      {children}
      <Toaster />
    </>
  );
}
