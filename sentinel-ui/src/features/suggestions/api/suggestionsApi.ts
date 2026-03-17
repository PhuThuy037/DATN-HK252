import { AxiosError } from "axios";
import { httpClient } from "@/shared/api/httpClient";
import type { ApiEnvelope } from "@/shared/types";
import type {
  ApiErrorBody,
  ApiErrorDetail,
  ApplySuggestionRequest,
  ConfirmSuggestionRequest,
  EditSuggestionRequest,
  GenerateSuggestionRequest,
  RejectSuggestionRequest,
  RuleSuggestionApplyOut,
  RuleSuggestionGenerateOut,
  RuleSuggestionGetOut,
  RuleSuggestionLogOut,
  RuleSuggestionOut,
  RuleSuggestionSimulateOut,
  SimulateSuggestionRequest,
  SuggestionListParams,
} from "@/features/suggestions/types";

type EnvelopeWithError<T> = ApiEnvelope<T> & {
  error: ApiErrorBody | null;
};

export class SuggestionApiError extends Error {
  status?: number;
  code?: string;
  details?: ApiErrorDetail[];

  constructor(
    message: string,
    options?: { status?: number; code?: string; details?: ApiErrorDetail[] }
  ) {
    super(message);
    this.name = "SuggestionApiError";
    this.status = options?.status;
    this.code = options?.code;
    this.details = options?.details;
  }
}

function toSuggestionApiError(
  fallbackMessage: string,
  options?: { status?: number; error?: ApiErrorBody | null }
) {
  return new SuggestionApiError(options?.error?.message ?? fallbackMessage, {
    status: options?.status,
    code: options?.error?.code,
    details: options?.error?.details,
  });
}

function unwrapEnvelope<T>(envelope: ApiEnvelope<T>, fallbackMessage: string) {
  const typedEnvelope = envelope as EnvelopeWithError<T>;
  if (!typedEnvelope.ok || typedEnvelope.data == null) {
    throw toSuggestionApiError(fallbackMessage, { error: typedEnvelope.error });
  }
  return typedEnvelope.data;
}

function normalizeError(error: unknown, fallbackMessage: string) {
  if (error instanceof SuggestionApiError) {
    return error;
  }

  const axiosError = error as AxiosError<EnvelopeWithError<unknown>>;
  const status = axiosError.response?.status;
  const serverError = axiosError.response?.data?.error ?? null;

  if (serverError) {
    return toSuggestionApiError(fallbackMessage, { status, error: serverError });
  }

  if (error instanceof Error) {
    return new SuggestionApiError(error.message, { status });
  }

  return new SuggestionApiError(fallbackMessage, { status });
}

export function getSuggestionErrorMessage(
  error: unknown,
  fallbackMessage = "Request failed"
) {
  if (error instanceof SuggestionApiError) {
    return error.message || fallbackMessage;
  }
  if (error instanceof Error) {
    return error.message || fallbackMessage;
  }
  return fallbackMessage;
}

export function isSuggestionApiError(error: unknown): error is SuggestionApiError {
  return error instanceof SuggestionApiError;
}

export async function generateSuggestion(
  ruleSetId: string,
  payload: GenerateSuggestionRequest
) {
  try {
    const response = await httpClient.post<ApiEnvelope<RuleSuggestionGenerateOut>>(
      `/v1/rule-sets/${ruleSetId}/rule-suggestions/generate`,
      payload
    );
    return unwrapEnvelope(response.data, "Failed to generate suggestion");
  } catch (error) {
    throw normalizeError(error, "Failed to generate suggestion");
  }
}

export async function getSuggestionList(
  ruleSetId: string,
  params?: SuggestionListParams
) {
  try {
    const response = await httpClient.get<ApiEnvelope<RuleSuggestionOut[]>>(
      `/v1/rule-sets/${ruleSetId}/rule-suggestions`,
      { params }
    );
    return unwrapEnvelope(response.data, "Failed to load suggestions");
  } catch (error) {
    throw normalizeError(error, "Failed to load suggestions");
  }
}

export async function getSuggestionDetail(ruleSetId: string, suggestionId: string) {
  try {
    const response = await httpClient.get<ApiEnvelope<RuleSuggestionGetOut>>(
      `/v1/rule-sets/${ruleSetId}/rule-suggestions/${suggestionId}`
    );
    return unwrapEnvelope(response.data, "Failed to load suggestion detail");
  } catch (error) {
    throw normalizeError(error, "Failed to load suggestion detail");
  }
}

export async function getSuggestionLogs(
  ruleSetId: string,
  suggestionId: string,
  params?: { limit?: number }
) {
  try {
    const response = await httpClient.get<ApiEnvelope<RuleSuggestionLogOut[]>>(
      `/v1/rule-sets/${ruleSetId}/rule-suggestions/${suggestionId}/logs`,
      { params }
    );
    return unwrapEnvelope(response.data, "Failed to load suggestion logs");
  } catch (error) {
    throw normalizeError(error, "Failed to load suggestion logs");
  }
}

export async function editSuggestion(
  ruleSetId: string,
  suggestionId: string,
  payload: EditSuggestionRequest
) {
  try {
    const response = await httpClient.patch<ApiEnvelope<RuleSuggestionOut>>(
      `/v1/rule-sets/${ruleSetId}/rule-suggestions/${suggestionId}`,
      payload
    );
    return unwrapEnvelope(response.data, "Failed to save draft");
  } catch (error) {
    throw normalizeError(error, "Failed to save draft");
  }
}

export async function confirmSuggestion(
  ruleSetId: string,
  suggestionId: string,
  payload: ConfirmSuggestionRequest
) {
  try {
    const response = await httpClient.post<ApiEnvelope<RuleSuggestionOut>>(
      `/v1/rule-sets/${ruleSetId}/rule-suggestions/${suggestionId}/confirm`,
      payload
    );
    return unwrapEnvelope(response.data, "Failed to confirm suggestion");
  } catch (error) {
    throw normalizeError(error, "Failed to confirm suggestion");
  }
}

export async function rejectSuggestion(
  ruleSetId: string,
  suggestionId: string,
  payload: RejectSuggestionRequest
) {
  try {
    const response = await httpClient.post<ApiEnvelope<RuleSuggestionOut>>(
      `/v1/rule-sets/${ruleSetId}/rule-suggestions/${suggestionId}/reject`,
      payload
    );
    return unwrapEnvelope(response.data, "Failed to reject suggestion");
  } catch (error) {
    throw normalizeError(error, "Failed to reject suggestion");
  }
}

export async function applySuggestion(
  ruleSetId: string,
  suggestionId: string,
  payload: ApplySuggestionRequest
) {
  try {
    const response = await httpClient.post<ApiEnvelope<RuleSuggestionApplyOut>>(
      `/v1/rule-sets/${ruleSetId}/rule-suggestions/${suggestionId}/apply`,
      payload
    );
    return unwrapEnvelope(response.data, "Failed to apply suggestion");
  } catch (error) {
    throw normalizeError(error, "Failed to apply suggestion");
  }
}

export async function simulateSuggestion(
  ruleSetId: string,
  suggestionId: string,
  payload: SimulateSuggestionRequest
) {
  try {
    const response = await httpClient.post<ApiEnvelope<RuleSuggestionSimulateOut>>(
      `/v1/rule-sets/${ruleSetId}/rule-suggestions/${suggestionId}/simulate`,
      payload
    );
    return unwrapEnvelope(response.data, "Failed to simulate suggestion");
  } catch (error) {
    throw normalizeError(error, "Failed to simulate suggestion");
  }
}
