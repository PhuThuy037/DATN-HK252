export const policyIngestStatuses = [
  "pending",
  "running",
  "success",
  "failed",
  "skipped",
] as const;

export type PolicyIngestStatus = (typeof policyIngestStatuses)[number];

export type PolicyDocument = {
  id: string;
  rule_set_id?: string | null;
  stable_key: string;
  title: string;
  doc_type: string;
  content_hash: string;
  version: number;
  enabled: boolean;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
};

export type PolicyIngestJob = {
  id: string;
  rule_set_id: string;
  requested_by: string;
  retry_of_job_id?: string | null;
  status: PolicyIngestStatus;
  total_items: number;
  success_items: number;
  failed_items: number;
  skipped_items: number;
  started_at?: string | null;
  finished_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type PolicyIngestJobItem = {
  id: string;
  stable_key: string;
  title: string;
  doc_type: string;
  content_hash: string;
  enabled: boolean;
  status: PolicyIngestStatus;
  document_id?: string | null;
  error_message?: string | null;
  attempt: number;
  created_at: string;
  updated_at: string;
};

export type PolicyIngestJobDetail = PolicyIngestJob & {
  error_json?: Record<string, unknown> | null;
  items: PolicyIngestJobItem[];
};

export type PolicyDocumentToggleEnabledPayload = {
  enabled: boolean;
};

export type PolicyIngestItemInput = {
  stable_key: string;
  title: string;
  content: string;
  doc_type?: string;
  enabled?: boolean;
};

export type CreatePolicyIngestJobRequest = {
  items: PolicyIngestItemInput[];
};

export type PolicyIngestJobsParams = {
  limit?: number;
};

export type PolicyApiErrorDetail = {
  field?: string | null;
  reason?: string;
  extra?: unknown;
};

export type PolicyApiErrorBody = {
  code: string;
  message: string;
  details?: PolicyApiErrorDetail[];
};
