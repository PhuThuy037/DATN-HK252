import { httpClient } from "@/shared/api/httpClient";
import type { ApiEnvelope } from "@/shared/types";
import type {
  AdminBlockMaskLogItem,
  AdminConversationDetail,
  AdminConversationMessagesPage,
  AdminConversationListItem,
  AdminPaginationMeta,
} from "@/features/admin-monitoring/types/adminMonitoringTypes";

type EnvelopeWithMeta<T> = ApiEnvelope<T> & {
  meta?: AdminPaginationMeta;
};

function unwrapEnvelope<T>(envelope: ApiEnvelope<T>, fallbackMessage: string) {
  if (!envelope.ok || !envelope.data) {
    throw new Error(envelope.error?.message ?? fallbackMessage);
  }
  return envelope.data;
}

function unwrapEnvelopeWithMeta<T>(
  envelope: EnvelopeWithMeta<T>,
  fallbackMessage: string
) {
  if (!envelope.ok || !envelope.data) {
    throw new Error(envelope.error?.message ?? fallbackMessage);
  }

  return {
    data: envelope.data,
    meta: envelope.meta ?? {},
  };
}

export async function getAdminConversations(params?: {
  limit?: number;
  cursor?: string | null;
  status?: string;
  q?: string;
}) {
  const response = await httpClient.get<
    EnvelopeWithMeta<AdminConversationListItem[]>
  >("/v1/admin/conversations", { params });

  return unwrapEnvelopeWithMeta(
    response.data,
    "Failed to load admin conversations"
  );
}

export async function getAdminConversation(conversationId: string) {
  const response = await httpClient.get<ApiEnvelope<AdminConversationDetail>>(
    `/v1/admin/conversations/${conversationId}`
  );

  return unwrapEnvelope(response.data, "Failed to load admin conversation");
}

export async function getAdminConversationMessages(
  conversationId: string,
  params?: {
    before_seq?: number;
    limit?: number;
  }
) {
  const response = await httpClient.get<ApiEnvelope<AdminConversationMessagesPage>>(
    `/v1/admin/conversations/${conversationId}/messages`,
    { params }
  );

  return unwrapEnvelope(response.data, "Failed to load admin messages");
}

export async function getAdminBlockMaskLogs(params?: {
  limit?: number;
  cursor?: string | null;
  action?: "mask" | "block";
}) {
  const response = await httpClient.get<
    EnvelopeWithMeta<AdminBlockMaskLogItem[]>
  >("/v1/admin/logs/block-mask", { params });

  return unwrapEnvelopeWithMeta(
    response.data,
    "Failed to load block and mask logs"
  );
}
