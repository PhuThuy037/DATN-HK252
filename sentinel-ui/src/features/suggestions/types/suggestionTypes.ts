export const suggestionStatuses = [
  "draft",
  "approved",
  "applied",
  "rejected",
  "expired",
  "failed",
] as const;

export type SuggestionStatus = (typeof suggestionStatuses)[number];
export type SuggestionStatusFilter = SuggestionStatus | "all";

export type SuggestionRule = {
  stable_key: string;
  name: string;
  description?: string | null;
  scope: string;
  action: string;
  severity: string;
  priority: number;
  rag_mode: string;
  enabled: boolean;
  conditions: Record<string, unknown>;
};

export type SuggestionContextTerm = {
  entity_type: string;
  term: string;
  lang: string;
  weight: number;
  window_1: number;
  window_2: number;
  enabled: boolean;
};

export type SuggestionDraft = {
  rule: SuggestionRule;
  context_terms: SuggestionContextTerm[];
};

export type SuggestionExplanation = {
  summary: string;
  detected_intent: string;
  derived_terms: string[];
  action_reason: string;
};

export type SuggestionQualitySignals = {
  intent_confidence: number;
  duplicate_risk: string;
  conflict_risk: string;
  generation_source: string;
  has_policy_context: boolean;
  intent_guard_applied: boolean;
  intent_mismatch_detected: boolean;
  runtime_usable: boolean;
  runtime_warnings: string[];
};

export type SuggestionDuplicateCandidate = {
  rule_id: string;
  stable_key: string;
  name: string;
  origin: string;
  similarity: number;
  lexical_score: number;
  action?: string | null;
  scope?: string | null;
  summary?: string | null;
};

export type SuggestionDuplicateCheck = {
  decision: string;
  confidence: number;
  rationale: string;
  matched_rule_ids: string[];
  candidates: SuggestionDuplicateCandidate[];
  top_k: number;
  exact_threshold: number;
  near_threshold: number;
  source: string;
  llm_provider?: string | null;
  llm_model?: string | null;
  llm_fallback_used: boolean;
};

export type SuggestionDuplicateLevel = "none" | "weak" | "strong";

export type SuggestionDuplicate = {
  level: SuggestionDuplicateLevel;
  reason: string;
  similar_rules: SuggestionDuplicateCandidate[];
};

export type SuggestionRetrievalContext = {
  has_policy_context: boolean;
  policy_chunk_ids: string[];
  related_rule_ids: string[];
};

export type RuleSuggestionOut = {
  id: string;
  rule_set_id: string;
  created_by: string;
  status: SuggestionStatus;
  type: string;
  version: number;
  nl_input: string;
  dedupe_key: string;
  draft: SuggestionDraft;
  applied_result_json?: Record<string, unknown> | null;
  expires_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type RuleSuggestionGenerateOut = RuleSuggestionOut & {
  duplicate: SuggestionDuplicate;
  duplicate_check: SuggestionDuplicateCheck;
  explanation: SuggestionExplanation;
  quality_signals: SuggestionQualitySignals;
  retrieval_context: SuggestionRetrievalContext;
};

export type RuleSuggestionGetOut = RuleSuggestionOut & {
  duplicate: SuggestionDuplicate;
  explanation: SuggestionExplanation;
  quality_signals: SuggestionQualitySignals;
};

export type RuleSuggestionApplyOut = {
  rule_id: string;
  rule_set_id: string;
  stable_key: string;
  name: string;
  action: string;
  origin: string;
  context_term_ids: string[];
};

export type RuleSuggestionLogOut = {
  id: string;
  suggestion_id: string;
  rule_set_id: string;
  actor_user_id: string;
  action: string;
  reason?: string | null;
  before_json?: Record<string, unknown> | null;
  after_json?: Record<string, unknown> | null;
  created_at: string;
};

export type SuggestionSimulateResult = {
  content: string;
  matched: boolean;
  predicted_action: "ALLOW" | "MASK" | "BLOCK";
};

export type RuleSuggestionSimulateOut = {
  suggestion_id: string;
  sample_size: number;
  runtime_usable: boolean;
  runtime_warnings: string[];
  matched_count: number;
  action_breakdown: {
    ALLOW: number;
    MASK: number;
    BLOCK: number;
  };
  results: SuggestionSimulateResult[];
};

export type GenerateSuggestionRequest = {
  prompt: string;
};

export type SuggestionListParams = {
  status?: SuggestionStatus;
  limit?: number;
};

export type EditSuggestionRequest = {
  draft: SuggestionDraft;
  expected_version: number;
};

export type ConfirmSuggestionRequest = {
  expected_version: number;
};

export type RejectSuggestionRequest = {
  reason?: string | null;
  expected_version: number;
};

export type ApplySuggestionRequest = {
  expected_version: number;
};

export type SimulateSuggestionRequest = {
  samples: string[];
  include_examples?: boolean;
};

export type ApiErrorDetail = {
  field?: string | null;
  reason?: string;
  extra?: unknown;
};

export type ApiErrorBody = {
  code: string;
  message: string;
  details?: ApiErrorDetail[];
};
