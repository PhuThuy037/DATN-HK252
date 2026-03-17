export type SystemPromptSettings = {
  rule_set_id: string;
  system_prompt: string | null;
};

export type UpdateSystemPromptPayload = {
  system_prompt: string | null;
};
