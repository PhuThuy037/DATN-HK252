import { create } from "zustand";
import type { RuleSetSummary } from "@/features/rules/types";

type RuleSetState = {
  currentRuleSetId: string | null;
  currentRuleSet: RuleSetSummary | null;
  isRuleSetResolved: boolean;
  setCurrentRuleSet: (ruleSet: RuleSetSummary | null) => void;
  clearCurrentRuleSet: () => void;
  setRuleSetResolved: (value: boolean) => void;
};

export const useRuleSetStore = create<RuleSetState>((set) => ({
  currentRuleSetId: null,
  currentRuleSet: null,
  isRuleSetResolved: false,
  setCurrentRuleSet: (ruleSet) =>
    set({
      currentRuleSet: ruleSet,
      currentRuleSetId: ruleSet?.id ?? null,
      isRuleSetResolved: true,
    }),
  clearCurrentRuleSet: () =>
    set({
      currentRuleSetId: null,
      currentRuleSet: null,
      isRuleSetResolved: true,
    }),
  setRuleSetResolved: (value) => set({ isRuleSetResolved: value }),
}));
