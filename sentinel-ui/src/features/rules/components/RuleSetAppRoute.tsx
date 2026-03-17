import { ReactNode, useEffect } from "react";
import { Navigate } from "react-router-dom";
import { useMyRuleSets } from "@/features/rules/hooks/useMyRuleSets";
import { useRuleSetStore } from "@/features/rules/store/ruleSetStore";

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
    return null;
  }

  if (myRuleSetsQuery.isLoading) {
    return null;
  }

  if (myRuleSetsQuery.isError) {
    return (
      <div className="flex h-screen items-center justify-center px-6">
        <p className="text-sm text-destructive">
          Failed to load your workspace. Please refresh and try again.
        </p>
      </div>
    );
  }

  if (!myRuleSetsQuery.data || myRuleSetsQuery.data.length === 0) {
    return <Navigate replace to="/onboarding/rule-set" />;
  }

  return <>{children}</>;
}
