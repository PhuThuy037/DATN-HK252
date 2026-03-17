import { useQuery } from "@tanstack/react-query";
import { getPolicyIngestJobDetail } from "@/features/policies/api/policiesApi";
import {
  activeIngestStatuses,
  policyQueryKeys,
} from "@/features/policies/hooks/queryKeys";
import type { PolicyIngestJobDetail } from "@/features/policies/types";

export function usePolicyIngestJobDetail(ruleSetId?: string, jobId?: string) {
  return useQuery({
    queryKey:
      ruleSetId && jobId
        ? policyQueryKeys.ingestJobDetail(ruleSetId, jobId)
        : ["policy-ingest-job-detail", "unknown"],
    queryFn: () => getPolicyIngestJobDetail(ruleSetId as string, jobId as string),
    enabled: Boolean(ruleSetId && jobId),
    refetchInterval: (query) => {
      const data = query.state.data as PolicyIngestJobDetail | undefined;
      if (!data) {
        return false;
      }
      return activeIngestStatuses.includes(data.status) ? 3000 : false;
    },
  });
}
