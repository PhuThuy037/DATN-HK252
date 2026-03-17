type UUID = string;

export type MessageRole = "system" | "user" | "assistant";

export type MessageListItem = {
  id: UUID;
  role: MessageRole;
  content?: string | null;
  content_masked?: string | null;
  created_at: string;
  state?: string | null;
};

export type MessagesPage = {
  items: MessageListItem[];
  page: {
    limit?: number;
    has_more: boolean;
    next_before_seq?: number | null;
    oldest_seq?: number | null;
    newest_seq?: number | null;
  };
};

export type MessageDetail = {
  id: UUID;
  conversation_id: UUID;
  role: MessageRole;
  sequence_number: number;
  input_type?: string | null;
  content?: string | null;
  content_masked?: string | null;
  scan_status?: string | null;
  final_action?: string | null;
  risk_score?: number | null;
  ambiguous?: boolean;
  matched_rule_ids?: string[];
  entities_json?: Record<string, unknown> | null;
  rag_evidence_json?: Record<string, unknown> | null;
  latency_ms?: number | null;
  blocked?: boolean;
  blocked_reason?: string | null;
  created_at: string;
};

export type SendMessageRequest = {
  content: string;
  input_type?: string;
};

export type SendMessageResponseData = {
  id: UUID;
  conversation_id: UUID;
  role: MessageRole;
  sequence_number: number;
  content?: string | null;
  content_masked?: string | null;
  final_action?: string | null;
  risk_score?: number | null;
  matched_rule_ids?: string[];
  entities_json?: Record<string, unknown> | null;
  rag_evidence_json?: Record<string, unknown> | null;
  blocked?: boolean;
  blocked_reason?: string | null;
  assistant_message_id?: UUID | null;
  created_at: string;
};
