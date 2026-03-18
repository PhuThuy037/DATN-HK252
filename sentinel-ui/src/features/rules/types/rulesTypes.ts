export type Rule = {
  id: string;
  rule_set_id?: string | null;
  stable_key?: string | null;
  name: string;
  description?: string | null;
  scope?: string | null;
  action: string;
  severity?: string | null;
  priority?: number | null;
  rag_mode?: string | null;
  enabled: boolean;
  origin?: string | null;
  can_edit_action?: boolean;
  can_soft_delete?: boolean;
  conditions?: Record<string, unknown> | null;
  conditions_version?: number | null;
  created_at?: string;
  updated_at?: string;
};

export type RuleContextTerm = {
  id: string;
  entity_type: string;
  term: string;
  lang: string;
  weight: number;
  window_1: number;
  window_2: number;
  enabled: boolean;
  created_at: string;
};

export type RuleDetail = {
  id: string;
  stable_key: string;
  name: string;
  description?: string | null;
  scope: string;
  conditions: Record<string, unknown>;
  action: string;
  severity: string;
  priority: number;
  rag_mode: string;
  enabled: boolean;
  context_terms: RuleContextTerm[];
  created_at: string;
  updated_at: string;
};

export type RuleChangeLog = {
  id?: string;
  rule_set_id?: string;
  rule_id?: string;
  actor_user_id?: string;
  action?: string;
  reason?: string | null;
  changed_fields?: string[];
  before_json?: Record<string, unknown> | null;
  after_json?: Record<string, unknown> | null;
  created_at?: string;
};

export type EffectiveRule = {
  id?: string;
  rule_id?: string;
  stable_key?: string | null;
  name: string;
  action: string;
  priority?: number | null;
  enabled?: boolean;
  origin?: string | null;
};

export type RuleSetSummary = {
  id: string;
  name?: string;
  status?: string;
  my_role?: string;
  created_at?: string;
};

export type CreateRuleSetRequest = {
  name: string;
};

export type RuleDebugMatch = {
  rule_id?: string;
  stable_key?: string | null;
  name?: string;
  action?: string;
  priority?: number;
};

export type DebugEvaluateRequest = {
  content: string;
};

export type DebugEvaluateResponse = {
  final_action?: string;
  matched_rules?: RuleDebugMatch[];
  signals?: Record<string, unknown>;
};

export type CreateRuleRequest = {
  stable_key: string;
  name: string;
  description?: string | null;
  scope?: string;
  conditions: Record<string, unknown>;
  action?: string;
  severity?: string;
  priority?: number;
  rag_mode?: string;
  enabled?: boolean;
};

export type UpdateRuleRequest = {
  name?: string;
  description?: string | null;
  scope?: string;
  conditions?: Record<string, unknown>;
  action?: string;
  severity?: string;
  priority?: number;
  rag_mode?: string;
  enabled?: boolean;
};

export type ToggleGlobalRuleRequest = {
  enabled: boolean;
};
