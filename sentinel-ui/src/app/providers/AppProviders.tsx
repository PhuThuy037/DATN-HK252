import { PropsWithChildren } from "react";
import { AppQueryProvider } from "@/app/providers/QueryProvider";
import { AppToastProvider } from "@/app/providers/ToastProvider";
import { ErrorBoundary } from "@/app/providers/ErrorBoundary";

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <ErrorBoundary>
      <AppQueryProvider>
        <AppToastProvider>{children}</AppToastProvider>
      </AppQueryProvider>
    </ErrorBoundary>
  );
}
