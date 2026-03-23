import { httpClient } from "@/shared/api/httpClient";
import type { ApiEnvelope } from "@/shared/types";
import type {
  CreateRuleRequest,
  CreateRuleSetRequest,
  DebugEvaluateRequest,
  DebugEvaluateResponse,
  EffectiveRule,
  RuleDetail,
  Rule,
  RuleChangeLog,
  RuleSetSummary,
  ToggleGlobalRuleRequest,
  UpdateRuleRequest,
} from "@/features/rules/types";

type RuleChangeLogsParams = {
  limit?: number;
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

export async function getEffectiveRules() {
  const response = await httpClient.get<ApiEnvelope<EffectiveRule[]>>(
    "/v1/rules/me/effective"
  );
  return unwrapEnvelope(response.data, "Failed to load effective rules");
}

export async function debugEvaluateText(payload: DebugEvaluateRequest) {
  const response = await httpClient.post<ApiEnvelope<DebugEvaluateResponse>>(
    "/v1/rules/debug/evaluate",
    payload
  );
  return unwrapEnvelope(response.data, "Failed to evaluate text");
}

export async function getRuleSetRules(ruleSetId: string) {
  const response = await httpClient.get<ApiEnvelope<Rule[]>>(
    `/v1/rule-sets/${ruleSetId}/rules`
  );
  return unwrapEnvelope(response.data, "Failed to load rules");
}

export async function getRuleDetail(ruleId: string) {
  const response = await httpClient.get<ApiEnvelope<RuleDetail>>(
    `/v1/rules/${ruleId}`
  );
  return unwrapEnvelope(response.data, "Failed to load rule detail");
}

export async function getRuleChangeLogs(
  ruleSetId: string,
  params?: RuleChangeLogsParams
) {
  const response = await httpClient.get<ApiEnvelope<RuleChangeLog[]>>(
    `/v1/rule-sets/${ruleSetId}/rules/change-logs`,
    { params }
  );
  return unwrapEnvelope(response.data, "Failed to load rule change logs");
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
