import { ReactNode, useEffect } from "react";
import { Navigate } from "react-router-dom";
import { useAuthStore } from "@/features/auth/store/authStore";
import { useMe } from "@/features/auth/hooks/useMe";
import { useRuleSetStore } from "@/features/rules/store/ruleSetStore";
import { AppLoadingState } from "@/shared/ui/app-loading-state";

type ProtectedRouteProps = {
  children: ReactNode;
};

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const hasHydrated = useAuthStore((state) => state.hasHydrated);
  const accessToken = useAuthStore((state) => state.accessToken);
  const clearCurrentRuleSet = useRuleSetStore((state) => state.clearCurrentRuleSet);
  const setRuleSetResolved = useRuleSetStore((state) => state.setRuleSetResolved);

  const meQuery = useMe({
    enabled: hasHydrated && isAuthenticated && Boolean(accessToken),
  });

  useEffect(() => {
    if (!isAuthenticated || !accessToken) {
      clearCurrentRuleSet();
      setRuleSetResolved(false);
    }
  }, [
    accessToken,
    clearCurrentRuleSet,
    isAuthenticated,
    setRuleSetResolved,
  ]);

  if (!hasHydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6">
        <AppLoadingState
          className="w-full max-w-md"
          description="Checking your session and preparing the workspace."
          title="Loading workspace"
        />
      </div>
    );
  }

  if (!isAuthenticated || !accessToken) {
    return <Navigate replace to="/login" />;
  }

  if (meQuery.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6">
        <AppLoadingState
          className="w-full max-w-md"
          description="Checking your session and preparing the workspace."
          title="Loading workspace"
        />
      </div>
    );
  }

  if (meQuery.isError) {
    return <Navigate replace to="/login" />;
  }

  return <>{children}</>;
}
