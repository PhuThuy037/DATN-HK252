import { httpClient } from "@/shared/api/httpClient";
import type { ApiEnvelope } from "@/shared/types";
import type {
  ConversationDetail,
  ConversationUpdatePayload,
  ConversationsPage,
  CreateConversationPayload,
} from "@/shared/types";

type GetConversationsParams = {
  limit?: number;
  status?: "active" | "archived";
};

function unwrapEnvelope<T>(envelope: ApiEnvelope<T>, fallbackMessage: string) {
  if (!envelope.ok || !envelope.data) {
    throw new Error(envelope.error?.message ?? fallbackMessage);
  }
  return envelope.data;
}

export async function getConversations(params?: GetConversationsParams) {
  const response = await httpClient.get<ApiEnvelope<ConversationsPage>>(
    "/v1/conversations",
    { params }
  );

  return unwrapEnvelope(response.data, "Failed to load conversations");
}

export async function getConversation(conversationId: string) {
  const response = await httpClient.get<ApiEnvelope<ConversationDetail>>(
    `/v1/conversations/${conversationId}`
  );

  return unwrapEnvelope(response.data, "Failed to load conversation");
}

export async function createPersonalConversation(payload?: CreateConversationPayload) {
  const response = await httpClient.post<ApiEnvelope<ConversationDetail>>(
    "/v1/conversations/personal",
    payload ?? {}
  );

  return unwrapEnvelope(response.data, "Failed to create conversation");
}

export async function updateConversation(
  conversationId: string,
  payload: ConversationUpdatePayload
) {
  const response = await httpClient.patch<ApiEnvelope<ConversationDetail>>(
    `/v1/conversations/${conversationId}`,
    payload
  );

  return unwrapEnvelope(response.data, "Failed to update conversation");
}

export async function deleteConversation(conversationId: string) {
  const response = await httpClient.delete<ApiEnvelope<{ id: string; status: string }>>(
    `/v1/conversations/${conversationId}`
  );

  return unwrapEnvelope(response.data, "Failed to delete conversation");
}
