import { ReactNode, useEffect } from "react";
import { Navigate } from "react-router-dom";
import { useMyRuleSets } from "@/features/rules/hooks/useMyRuleSets";
import { useRuleSetStore } from "@/features/rules/store/ruleSetStore";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppLoadingState } from "@/shared/ui/app-loading-state";

type RuleSetAppRouteProps = {
  children: ReactNode;
};

export function RuleSetAppRoute({ children }: RuleSetAppRouteProps) {
  const setCurrentRuleSet = useRuleSetStore((state) => state.setCurrentRuleSet);
  const clearCurrentRuleSet = useRuleSetStore((state) => state.clearCurrentRuleSet);
  const setRuleSetResolved = useRuleSetStore((state) => state.setRuleSetResolved);

  const myRuleSetsQuery = useMyRuleSets();

  useEffect(() => {
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
    if (myRuleSetsQuery.isError) {
      setRuleSetResolved(true);
    }
  }, [myRuleSetsQuery.isError, setRuleSetResolved]);

  if (!myRuleSetsQuery.isFetchedAfterMount && !myRuleSetsQuery.isError) {
    return (
      <div className="flex h-screen items-center justify-center px-6">
        <AppLoadingState
          className="w-full max-w-md"
          description="We are finding the active workspace for this account."
          title="Loading workspace"
        />
      </div>
    );
  }

  if (myRuleSetsQuery.isLoading) {
    return (
      <div className="flex h-screen items-center justify-center px-6">
        <AppLoadingState
          className="w-full max-w-md"
          description="We are finding the active workspace for this account."
          title="Loading workspace"
        />
      </div>
    );
  }

  if (myRuleSetsQuery.isError) {
    return (
      <div className="flex h-screen items-center justify-center px-6">
        <AppAlert
          className="w-full max-w-md"
          description="Please refresh and try again."
          title="We couldn't load your workspace"
          variant="error"
        />
      </div>
    );
  }

  if (!myRuleSetsQuery.data || myRuleSetsQuery.data.length === 0) {
    return <Navigate replace to="/onboarding/rule-set" />;
  }

  return <>{children}</>;
}
