export const settingsQueryKeys = {
  systemPrompt: (ruleSetId: string) => ["system-prompt", ruleSetId] as const,
};
