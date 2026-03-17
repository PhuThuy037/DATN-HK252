import { useQuery } from "@tanstack/react-query";
import { getPolicyDocuments } from "@/features/policies/api/policiesApi";
import { policyQueryKeys } from "@/features/policies/hooks/queryKeys";

export function usePolicyDocuments(ruleSetId?: string) {
  return useQuery({
    queryKey: ruleSetId
      ? policyQueryKeys.documents(ruleSetId)
      : ["policy-documents", "unknown"],
    queryFn: () => getPolicyDocuments(ruleSetId as string),
    enabled: Boolean(ruleSetId),
  });
}
