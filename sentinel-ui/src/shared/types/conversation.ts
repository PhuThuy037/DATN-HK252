type UUID = string;

export type ConversationStatus = "active" | "archived";

export type ConversationListItem = {
  id: UUID;
  rule_set_id?: UUID | null;
  title?: string | null;
  status: ConversationStatus;
  model_name?: string | null;
  temperature?: number | null;
  last_sequence_number: number;
  created_at: string;
  updated_at: string;
  last_message_at?: string | null;
  last_message_preview?: string | null;
};

export type ConversationDetail = {
  id: UUID;
  user_id: UUID;
  rule_set_id?: UUID | null;
  title?: string | null;
  status: ConversationStatus;
  model_name?: string | null;
  temperature?: number | null;
  last_sequence_number: number;
  created_at: string;
  updated_at: string;
};

export type ConversationsPage = {
  items: ConversationListItem[];
  page: {
    limit: number;
    has_more: boolean;
    next_before_updated_at?: string | null;
    next_before_id?: UUID | null;
    status?: string;
  };
};

export type CreateConversationPayload = {
  title?: string;
  model_name?: string;
  temperature?: number;
};

export type ConversationUpdatePayload = {
  title?: string | null;
  status?: ConversationStatus;
};
