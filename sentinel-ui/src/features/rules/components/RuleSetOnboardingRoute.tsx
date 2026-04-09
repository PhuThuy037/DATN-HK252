import { ReactNode, useEffect } from "react";
import { useAuthStore } from "@/features/auth/store/authStore";
import { Navigate } from "react-router-dom";
import { useMyRuleSets } from "@/features/rules/hooks/useMyRuleSets";
import { useRuleSetStore } from "@/features/rules/store/ruleSetStore";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppLoadingState } from "@/shared/ui/app-loading-state";

type RuleSetOnboardingRouteProps = {
  children: ReactNode;
};

export function RuleSetOnboardingRoute({ children }: RuleSetOnboardingRouteProps) {
  const user = useAuthStore((state) => state.user);
  const isAdmin = user?.role === "admin";
  const setCurrentRuleSet = useRuleSetStore((state) => state.setCurrentRuleSet);
  const clearCurrentRuleSet = useRuleSetStore((state) => state.clearCurrentRuleSet);
  const setRuleSetResolved = useRuleSetStore((state) => state.setRuleSetResolved);

  const myRuleSetsQuery = useMyRuleSets({ enabled: isAdmin });

  useEffect(() => {
    if (!isAdmin) {
      clearCurrentRuleSet();
      setRuleSetResolved(true);
    }
  }, [clearCurrentRuleSet, isAdmin, setRuleSetResolved]);

  useEffect(() => {
    if (!isAdmin) {
      return;
    }
    if (myRuleSetsQuery.isSuccess) {
      const firstRuleSet = myRuleSetsQuery.data[0] ?? null;
      if (firstRuleSet) {
        setCurrentRuleSet(firstRuleSet);
      } else {
        clearCurrentRuleSet();
      }
    }
  }, [
    clearCurrentRuleSet,
    myRuleSetsQuery.data,
    myRuleSetsQuery.isSuccess,
    setCurrentRuleSet,
  ]);

  useEffect(() => {
    if (!isAdmin) {
      return;
    }
    if (myRuleSetsQuery.isError) {
      setRuleSetResolved(true);
    }
  }, [isAdmin, myRuleSetsQuery.isError, setRuleSetResolved]);

  if (!isAdmin) {
    return <Navigate replace to="/app/chat" />;
  }

  if (!myRuleSetsQuery.isFetchedAfterMount && !myRuleSetsQuery.isError) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6">
        <AppLoadingState
          className="w-full max-w-md"
          description="We are checking whether this account already has a workspace."
          title="Loading workspace"
        />
      </div>
    );
  }

  if (myRuleSetsQuery.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6">
        <AppLoadingState
          className="w-full max-w-md"
          description="We are checking whether this account already has a workspace."
          title="Loading workspace"
        />
      </div>
    );
  }

  if (myRuleSetsQuery.isError) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6">
        <AppAlert
          className="w-full max-w-md"
          description="Please refresh and try again."
          title="We couldn't load your workspace details"
          variant="error"
        />
      </div>
    );
  }

  if (myRuleSetsQuery.data && myRuleSetsQuery.data.length > 0) {
    return <Navigate replace to="/app/chat" />;
  }

  return <>{children}</>;
}
