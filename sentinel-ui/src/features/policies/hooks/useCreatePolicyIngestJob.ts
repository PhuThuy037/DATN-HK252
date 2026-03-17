import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createPolicyIngestJob } from "@/features/policies/api/policiesApi";
import { policyQueryKeys } from "@/features/policies/hooks/queryKeys";
import type { CreatePolicyIngestJobRequest } from "@/features/policies/types";

export function useCreatePolicyIngestJob(ruleSetId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: CreatePolicyIngestJobRequest) =>
      createPolicyIngestJob(ruleSetId as string, payload),
    onSuccess: () => {
      if (!ruleSetId) {
        return;
      }
      queryClient.invalidateQueries({
        queryKey: policyQueryKeys.ingestJobsBase(ruleSetId),
      });
      queryClient.invalidateQueries({
        queryKey: policyQueryKeys.documents(ruleSetId),
      });
    },
  });
}
