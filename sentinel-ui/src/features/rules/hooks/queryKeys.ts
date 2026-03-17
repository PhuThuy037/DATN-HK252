export const ruleQueryKeys = {
  myRuleSets: ["my-rule-sets"] as const,
  rules: (ruleSetId: string) => ["rules", ruleSetId] as const,
  effectiveRules: ["effective-rules"] as const,
  ruleChangeLogs: (ruleSetId: string) => ["rule-change-logs", ruleSetId] as const,
  ruleDebugEvaluate: ["rule-debug-evaluate"] as const,
};
