import { httpClient } from "@/shared/api/httpClient";
import type { ApiEnvelope } from "@/shared/types";
import type {
  CreateRuleRequest,
  CreateRuleSetRequest,
  DebugEvaluateRequest,
  DebugEvaluateResponse,
  EffectiveRule,
  PaginatedResult,
  PaginationMeta,
  RuleDetail,
  RuleListTab,
  Rule,
  RuleChangeLog,
  RuleSetSummary,
  ToggleGlobalRuleRequest,
  UpdateRuleRequest,
} from "@/features/rules/types";

type PaginationParams = {
  limit?: number;
  cursor?: string;
};

type RuleSetRulesParams = PaginationParams & {
  tab?: RuleListTab;
};

function unwrapEnvelope<T>(envelope: ApiEnvelope<T>, fallbackMessage: string) {
  if (!envelope.ok || !envelope.data) {
    const error = new Error(envelope.error?.message ?? fallbackMessage) as Error & {
      response?: { data?: unknown };
    };
    error.response = { data: envelope };
    throw error;
  }
  return envelope.data;
}

function unwrapEnvelopeWithMeta<T>(envelope: ApiEnvelope<T>, fallbackMessage: string) {
  const data = unwrapEnvelope(envelope, fallbackMessage);
  const meta = (envelope.meta ?? {}) as PaginationMeta;
  return { data, meta };
}

function toNullableNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function toPaginatedResult<T>(items: T[], rawMeta?: PaginationMeta): PaginatedResult<T> {
  const nextCursorRaw =
    typeof rawMeta?.next_cursor === "string" ? rawMeta.next_cursor.trim() : "";
  const hasMore = Boolean(rawMeta?.has_more);
  return {
    items,
    nextCursor: nextCursorRaw ? nextCursorRaw : null,
    hasMore,
    total: toNullableNumber(rawMeta?.total),
    limit: toNullableNumber(rawMeta?.limit),
  };
}

export async function getMyRuleSets() {
  const response = await httpClient.get<ApiEnvelope<RuleSetSummary[]>>(
    "/v1/rule-sets/me"
  );
  return unwrapEnvelope(response.data, "Failed to load rule sets");
}

export async function createRuleSet(payload: CreateRuleSetRequest) {
  const response = await httpClient.post<ApiEnvelope<RuleSetSummary>>(
    "/v1/rule-sets",
    payload
  );
  return unwrapEnvelope(response.data, "Failed to create rule set");
}

export async function getEffectiveRules(params?: PaginationParams) {
  const response = await httpClient.get<ApiEnvelope<EffectiveRule[]>>(
    "/v1/rules/me/effective",
    { params }
  );
  const { data, meta } = unwrapEnvelopeWithMeta(
    response.data,
    "Failed to load effective rules"
  );
  return toPaginatedResult(data, meta);
}

export async function debugEvaluateText(payload: DebugEvaluateRequest) {
  const response = await httpClient.post<ApiEnvelope<DebugEvaluateResponse>>(
    "/v1/rules/debug/evaluate",
    payload
  );
  return unwrapEnvelope(response.data, "Failed to evaluate text");
}

export async function getRuleSetRules(ruleSetId: string, params?: RuleSetRulesParams) {
  const response = await httpClient.get<ApiEnvelope<Rule[]>>(
    `/v1/rule-sets/${ruleSetId}/rules`,
    { params }
  );
  const { data, meta } = unwrapEnvelopeWithMeta(
    response.data,
    "Failed to load rules"
  );
  return toPaginatedResult(data, meta);
}

export async function getRuleDetail(ruleId: string) {
  const response = await httpClient.get<ApiEnvelope<RuleDetail>>(
    `/v1/rules/${ruleId}`
  );
  return unwrapEnvelope(response.data, "Failed to load rule detail");
}

export async function getRuleChangeLogs(
  ruleSetId: string,
  params?: PaginationParams
) {
  const response = await httpClient.get<ApiEnvelope<RuleChangeLog[]>>(
    `/v1/rule-sets/${ruleSetId}/rules/change-logs`,
    { params }
  );
  const { data, meta } = unwrapEnvelopeWithMeta(
    response.data,
    "Failed to load rule change logs"
  );
  return toPaginatedResult(data, meta);
}

export async function createRule(ruleSetId: string, payload: CreateRuleRequest) {
  const response = await httpClient.post<ApiEnvelope<Rule>>(
    `/v1/rule-sets/${ruleSetId}/rules`,
    payload
  );
  return unwrapEnvelope(response.data, "Failed to create rule");
}

export async function updateRule(
  ruleSetId: string,
  ruleId: string,
  payload: UpdateRuleRequest
) {
  const response = await httpClient.patch<ApiEnvelope<Rule>>(
    `/v1/rule-sets/${ruleSetId}/rules/${ruleId}`,
    payload
  );
  return unwrapEnvelope(response.data, "Failed to update rule");
}

export async function deleteRule(ruleSetId: string, ruleId: string) {
  const response = await httpClient.delete<ApiEnvelope<Rule>>(
    `/v1/rule-sets/${ruleSetId}/rules/${ruleId}`
  );
  return unwrapEnvelope(response.data, "Failed to delete rule");
}

export async function toggleGlobalRule(
  ruleSetId: string,
  stableKey: string,
  payload: ToggleGlobalRuleRequest
) {
  const response = await httpClient.patch<ApiEnvelope<Rule>>(
    `/v1/rule-sets/${ruleSetId}/rules/global/${stableKey}/enabled`,
    payload
  );
  return unwrapEnvelope(response.data, "Failed to toggle global rule");
}
