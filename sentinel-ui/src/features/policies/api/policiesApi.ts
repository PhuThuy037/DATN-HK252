import { AxiosError } from "axios";
import { httpClient } from "@/shared/api/httpClient";
import type { ApiEnvelope } from "@/shared/types";
import type {
  CreatePolicyIngestJobRequest,
  PolicyApiErrorBody,
  PolicyApiErrorDetail,
  PolicyDocument,
  PolicyDocumentToggleEnabledPayload,
  PolicyIngestJob,
  PolicyIngestJobDetail,
  PolicyIngestJobsParams,
} from "@/features/policies/types";

type EnvelopeWithError<T> = ApiEnvelope<T> & {
  error: PolicyApiErrorBody | null;
};

export class PolicyApiError extends Error {
  status?: number;
  code?: string;
  details?: PolicyApiErrorDetail[];

  constructor(
    message: string,
    options?: { status?: number; code?: string; details?: PolicyApiErrorDetail[] }
  ) {
    super(message);
    this.name = "PolicyApiError";
    this.status = options?.status;
    this.code = options?.code;
    this.details = options?.details;
  }
}

function toPolicyApiError(
  fallbackMessage: string,
  options?: { status?: number; error?: PolicyApiErrorBody | null }
) {
  return new PolicyApiError(options?.error?.message ?? fallbackMessage, {
    status: options?.status,
    code: options?.error?.code,
    details: options?.error?.details,
  });
}

function unwrapEnvelope<T>(envelope: ApiEnvelope<T>, fallbackMessage: string) {
  const typedEnvelope = envelope as EnvelopeWithError<T>;
  if (!typedEnvelope.ok || typedEnvelope.data == null) {
    throw toPolicyApiError(fallbackMessage, { error: typedEnvelope.error });
  }
  return typedEnvelope.data;
}

function normalizeError(error: unknown, fallbackMessage: string) {
  if (error instanceof PolicyApiError) {
    return error;
  }

  const axiosError = error as AxiosError<EnvelopeWithError<unknown>>;
  const status = axiosError.response?.status;
  const serverError = axiosError.response?.data?.error ?? null;

  if (serverError) {
    return toPolicyApiError(fallbackMessage, { status, error: serverError });
  }

  if (error instanceof Error) {
    return new PolicyApiError(error.message, { status });
  }

  return new PolicyApiError(fallbackMessage, { status });
}

export function getPolicyErrorMessage(error: unknown, fallback = "Request failed") {
  if (error instanceof PolicyApiError) {
    return error.message || fallback;
  }
  if (error instanceof Error) {
    return error.message || fallback;
  }
  return fallback;
}

export function isPolicyApiError(error: unknown): error is PolicyApiError {
  return error instanceof PolicyApiError;
}

export async function getPolicyDocuments(ruleSetId: string) {
  try {
    const response = await httpClient.get<ApiEnvelope<PolicyDocument[]>>(
      `/v1/rule-sets/${ruleSetId}/policy-documents`
    );
    return unwrapEnvelope(response.data, "Failed to load policy documents");
  } catch (error) {
    throw normalizeError(error, "Failed to load policy documents");
  }
}

export async function togglePolicyDocumentEnabled(
  ruleSetId: string,
  documentId: string,
  payload: PolicyDocumentToggleEnabledPayload
) {
  try {
    const response = await httpClient.patch<ApiEnvelope<PolicyDocument>>(
      `/v1/rule-sets/${ruleSetId}/policy-documents/${documentId}/enabled`,
      payload
    );
    return unwrapEnvelope(response.data, "Failed to update document enabled state");
  } catch (error) {
    throw normalizeError(error, "Failed to update document enabled state");
  }
}

export async function deletePolicyDocument(ruleSetId: string, documentId: string) {
  try {
    const response = await httpClient.delete<ApiEnvelope<PolicyDocument>>(
      `/v1/rule-sets/${ruleSetId}/policy-documents/${documentId}`
    );
    return unwrapEnvelope(response.data, "Failed to delete policy document");
  } catch (error) {
    throw normalizeError(error, "Failed to delete policy document");
  }
}

export async function createPolicyIngestJob(
  ruleSetId: string,
  payload: CreatePolicyIngestJobRequest
) {
  try {
    const response = await httpClient.post<ApiEnvelope<PolicyIngestJob>>(
      `/v1/rule-sets/${ruleSetId}/policy-ingest-jobs`,
      payload
    );
    return unwrapEnvelope(response.data, "Failed to create ingest job");
  } catch (error) {
    throw normalizeError(error, "Failed to create ingest job");
  }
}

export async function getPolicyIngestJobs(
  ruleSetId: string,
  params?: PolicyIngestJobsParams
) {
  try {
    const response = await httpClient.get<ApiEnvelope<PolicyIngestJob[]>>(
      `/v1/rule-sets/${ruleSetId}/policy-ingest-jobs`,
      { params }
    );
    return unwrapEnvelope(response.data, "Failed to load ingest jobs");
  } catch (error) {
    throw normalizeError(error, "Failed to load ingest jobs");
  }
}

export async function getPolicyIngestJobDetail(ruleSetId: string, jobId: string) {
  try {
    const response = await httpClient.get<ApiEnvelope<PolicyIngestJobDetail>>(
      `/v1/rule-sets/${ruleSetId}/policy-ingest-jobs/${jobId}`
    );
    return unwrapEnvelope(response.data, "Failed to load ingest job detail");
  } catch (error) {
    throw normalizeError(error, "Failed to load ingest job detail");
  }
}

export async function retryPolicyIngestJob(ruleSetId: string, jobId: string) {
  try {
    const response = await httpClient.post<ApiEnvelope<PolicyIngestJob>>(
      `/v1/rule-sets/${ruleSetId}/policy-ingest-jobs/${jobId}/retry`
    );
    return unwrapEnvelope(response.data, "Failed to retry ingest job");
  } catch (error) {
    throw normalizeError(error, "Failed to retry ingest job");
  }
}
