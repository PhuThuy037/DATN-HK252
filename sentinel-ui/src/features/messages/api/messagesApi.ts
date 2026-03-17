import { httpClient } from "@/shared/api/httpClient";
import type { ApiEnvelope } from "@/shared/types";
import type {
  MessageDetail,
  MessagesPage,
  SendMessageRequest,
  SendMessageResponseData,
} from "@/shared/types";

type GetMessagesParams = {
  before_seq?: number;
  limit?: number;
};

function unwrapEnvelope<T>(envelope: ApiEnvelope<T>, fallbackMessage: string) {
  if (!envelope.ok || !envelope.data) {
    throw new Error(envelope.error?.message ?? fallbackMessage);
  }
  return envelope.data;
}

function unwrapSendEnvelope(
  envelope: ApiEnvelope<SendMessageResponseData>,
  fallbackMessage: string
) {
  // Backend can return ok=false with data when a message is blocked by policy.
  if (envelope.data) {
    return envelope.data;
  }
  throw new Error(envelope.error?.message ?? fallbackMessage);
}

export async function getMessages(
  conversationId: string,
  params?: GetMessagesParams
) {
  const response = await httpClient.get<ApiEnvelope<MessagesPage>>(
    `/v1/conversations/${conversationId}/messages`,
    { params }
  );

  return unwrapEnvelope(response.data, "Failed to load messages");
}

export async function getMessageDetail(
  conversationId: string,
  messageId: string
) {
  const response = await httpClient.get<ApiEnvelope<MessageDetail>>(
    `/v1/conversations/${conversationId}/messages/${messageId}`
  );

  return unwrapEnvelope(response.data, "Failed to load message detail");
}

export async function sendMessage(
  conversationId: string,
  payload: SendMessageRequest
) {
  const response = await httpClient.post<ApiEnvelope<SendMessageResponseData>>(
    `/v1/conversations/${conversationId}/messages`,
    {
      content: payload.content,
      input_type: payload.input_type ?? "user_input",
    }
  );

  return unwrapSendEnvelope(response.data, "Failed to send message");
}
