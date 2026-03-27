export const ruleQueryKeys = {
  myRuleSets: ["my-rule-sets"] as const,
  rulesRoot: (ruleSetId: string) => ["rules", ruleSetId] as const,
  rules: (ruleSetId: string, tab: string, limit: number) =>
    ["rules", ruleSetId, tab, limit] as const,
  effectiveRulesRoot: ["effective-rules"] as const,
  effectiveRules: (limit: number) => ["effective-rules", limit] as const,
  ruleChangeLogsRoot: (ruleSetId: string) => ["rule-change-logs", ruleSetId] as const,
  ruleChangeLogs: (ruleSetId: string, limit: number) =>
    ["rule-change-logs", ruleSetId, limit] as const,
  ruleDebugEvaluate: ["rule-debug-evaluate"] as const,
};
