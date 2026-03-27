import type { SuggestionDuplicateCandidate } from "@/features/suggestions/types";
import { DuplicateRuleCard } from "@/features/suggestions/components/DuplicateRuleCard";

type DuplicateListProps = {
  candidates: SuggestionDuplicateCandidate[];
  highlightTerms?: string[];
  onViewRule?: (candidate: SuggestionDuplicateCandidate) => void;
  onCompareRule?: (candidate: SuggestionDuplicateCandidate) => void;
};

export function DuplicateList({
  candidates,
  highlightTerms = [],
  onViewRule,
  onCompareRule,
}: DuplicateListProps) {
  if (candidates.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3" id="suggestion-duplicate-list">
      <p className="text-sm font-medium text-foreground">
        {candidates.length} similar rule{candidates.length > 1 ? "s" : ""} to review
      </p>
      <div className="grid gap-3">
        {candidates.map((candidate) => (
          <DuplicateRuleCard
            candidate={candidate}
            highlightTerms={highlightTerms}
            key={candidate.rule_id}
            onCompareRule={onCompareRule}
            onViewRule={onViewRule}
          />
        ))}
      </div>
    </div>
  );
}
