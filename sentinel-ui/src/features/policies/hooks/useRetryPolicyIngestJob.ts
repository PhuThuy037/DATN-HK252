import { useMutation, useQueryClient } from "@tanstack/react-query";
import { retryPolicyIngestJob } from "@/features/policies/api/policiesApi";
import { policyQueryKeys } from "@/features/policies/hooks/queryKeys";

export function useRetryPolicyIngestJob(ruleSetId?: string, jobId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => retryPolicyIngestJob(ruleSetId as string, jobId as string),
    onSuccess: () => {
      if (!ruleSetId || !jobId) {
        return;
      }
      queryClient.invalidateQueries({
        queryKey: policyQueryKeys.ingestJobsBase(ruleSetId),
      });
      queryClient.invalidateQueries({
        queryKey: policyQueryKeys.ingestJobDetail(ruleSetId, jobId),
      });
    },
  });
}
