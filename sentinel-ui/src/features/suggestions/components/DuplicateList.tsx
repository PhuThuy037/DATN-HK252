import type { SuggestionDuplicateCandidate } from "@/features/suggestions/types";
import { DuplicateRuleCard } from "@/features/suggestions/components/DuplicateRuleCard";

type DuplicateListProps = {
  candidates: SuggestionDuplicateCandidate[];
  onViewRule?: (candidate: SuggestionDuplicateCandidate) => void;
  onCompareRule?: (candidate: SuggestionDuplicateCandidate) => void;
};

export function DuplicateList({
  candidates,
  onViewRule,
  onCompareRule,
}: DuplicateListProps) {
  if (candidates.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3" id="suggestion-duplicate-list">
      <p className="text-sm font-medium">
        {candidates.length} similar rule{candidates.length > 1 ? "s" : ""} found
      </p>
      <div className="space-y-2">
        {candidates.map((candidate) => (
          <DuplicateRuleCard
            candidate={candidate}
            key={candidate.rule_id}
            onCompareRule={onCompareRule}
            onViewRule={onViewRule}
          />
        ))}
      </div>
    </div>
  );
}
