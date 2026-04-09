export type AdminPaginationMeta = {
  next_cursor?: string | null;
  has_more?: boolean | null;
  total?: number | null;
  limit?: number | null;
};

export type AdminMatchedRule = {
  rule_id?: string | null;
  stable_key?: string | null;
  name?: string | null;
  action?: string | null;
  priority?: number | null;
};

export type AdminConversationListItem = {
  id: string;
  user_id: string;
  user_email: string;
  user_name?: string | null;
  rule_set_id?: string | null;
  title?: string | null;
  status: string;
  model_name?: string | null;
  temperature?: number | null;
  last_sequence_number: number;
  created_at: string;
  updated_at: string;
  last_message_at?: string | null;
  last_message_preview?: string | null;
  message_count: number;
  block_count: number;
  mask_count: number;
  has_sensitive_action: boolean;
};

export type AdminConversationDetail = {
  id: string;
  user_id: string;
  user_email: string;
  user_name?: string | null;
  rule_set_id?: string | null;
  title?: string | null;
  status: string;
  model_name?: string | null;
  temperature?: number | null;
  last_sequence_number: number;
  created_at: string;
  updated_at: string;
  message_count: number;
  block_count: number;
  mask_count: number;
};

export type AdminBlockMaskLogItem = {
  message_id: string;
  conversation_id: string;
  user_id: string;
  user_email: string;
  user_name?: string | null;
  conversation_title?: string | null;
  role: string;
  input_type?: string | null;
  action: string;
  summary?: string | null;
  content?: string | null;
  content_masked?: string | null;
  matched_rule_ids?: string[] | null;
  matched_rules?: AdminMatchedRule[] | null;
  risk_score?: number | null;
  blocked: boolean;
  created_at: string;
};

export type AdminMessageDetail = {
  id: string;
  conversation_id: string;
  role: "system" | "user" | "assistant";
  sequence_number: number;
  input_type?: string | null;
  content?: string | null;
  content_masked?: string | null;
  scan_status?: string | null;
  final_action?: string | null;
  risk_score?: number | null;
  ambiguous?: boolean;
  matched_rule_ids?: string[] | null;
  matched_rules?: AdminMatchedRule[] | null;
  entities_json?: Record<string, unknown> | null;
  rag_evidence_json?: Record<string, unknown> | null;
  latency_ms?: number | null;
  blocked?: boolean;
  blocked_reason?: string | null;
  created_at: string;
};

export type AdminConversationMessagesPage = {
  items: AdminMessageDetail[];
  page: {
    limit?: number;
    has_more: boolean;
    next_before_seq?: number | null;
    oldest_seq?: number | null;
    newest_seq?: number | null;
  };
};
