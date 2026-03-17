import type { PolicyIngestStatus } from "@/features/policies/types";

export const policyQueryKeys = {
  documents: (ruleSetId: string) => ["policy-documents", ruleSetId] as const,
  ingestJobs: (ruleSetId: string, limit?: number) =>
    ["policy-ingest-jobs", ruleSetId, limit ?? null] as const,
  ingestJobsBase: (ruleSetId: string) => ["policy-ingest-jobs", ruleSetId] as const,
  ingestJobDetail: (ruleSetId: string, jobId: string) =>
    ["policy-ingest-job-detail", ruleSetId, jobId] as const,
};

export const activeIngestStatuses: PolicyIngestStatus[] = ["pending", "running"];
