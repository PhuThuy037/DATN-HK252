import { httpClient } from "@/shared/api/httpClient";
import type { ApiEnvelope } from "@/shared/types";
import type {
  SystemPromptSettings,
  UpdateSystemPromptPayload,
} from "@/features/settings/types";

function unwrapEnvelope<T>(envelope: ApiEnvelope<T>, fallbackMessage: string) {
  if (!envelope.ok || envelope.data == null) {
    throw new Error(envelope.error?.message ?? fallbackMessage);
  }
  return envelope.data;
}

export async function getSystemPrompt(ruleSetId: string) {
  const response = await httpClient.get<ApiEnvelope<SystemPromptSettings>>(
    `/v1/rule-sets/${ruleSetId}/settings/system-prompt`
  );
  return unwrapEnvelope(response.data, "Failed to load system prompt");
}

export async function updateSystemPrompt(
  ruleSetId: string,
  payload: UpdateSystemPromptPayload
) {
  const response = await httpClient.put<ApiEnvelope<SystemPromptSettings>>(
    `/v1/rule-sets/${ruleSetId}/settings/system-prompt`,
    payload
  );
  return unwrapEnvelope(response.data, "Failed to update system prompt");
}
