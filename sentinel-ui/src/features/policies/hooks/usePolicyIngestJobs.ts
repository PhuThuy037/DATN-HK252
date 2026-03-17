import { useQuery } from "@tanstack/react-query";
import { getPolicyIngestJobs } from "@/features/policies/api/policiesApi";
import {
  activeIngestStatuses,
  policyQueryKeys,
} from "@/features/policies/hooks/queryKeys";
import type { PolicyIngestJob } from "@/features/policies/types";

export function usePolicyIngestJobs(ruleSetId?: string, limit = 50) {
  return useQuery({
    queryKey: ruleSetId
      ? policyQueryKeys.ingestJobs(ruleSetId, limit)
      : ["policy-ingest-jobs", "unknown"],
    queryFn: () => getPolicyIngestJobs(ruleSetId as string, { limit }),
    enabled: Boolean(ruleSetId),
    refetchInterval: (query) => {
      const data = query.state.data as PolicyIngestJob[] | undefined;
      if (!data || data.length === 0) {
        return false;
      }

      const hasActive = data.some((job) => activeIngestStatuses.includes(job.status));
      return hasActive ? 3000 : false;
    },
  });
}
