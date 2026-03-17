import type { SuggestionStatus } from "@/features/suggestions/types";

export const suggestionQueryKeys = {
  all: ["suggestions"] as const,
  listBase: (ruleSetId: string) => ["suggestions", "list", ruleSetId] as const,
  list: (ruleSetId: string, status?: SuggestionStatus, limit?: number) =>
    ["suggestions", "list", ruleSetId, status ?? null, limit ?? null] as const,
  detail: (ruleSetId: string, suggestionId: string) =>
    ["suggestions", "detail", ruleSetId, suggestionId] as const,
  logsBase: (ruleSetId: string, suggestionId: string) =>
    ["suggestions", "logs", ruleSetId, suggestionId] as const,
  logs: (ruleSetId: string, suggestionId: string, limit?: number) =>
    ["suggestions", "logs", ruleSetId, suggestionId, limit ?? null] as const,
};
