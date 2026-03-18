import type { SuggestionDuplicateCandidate } from "@/features/suggestions/types";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import {
  getSimilarityMeta,
  SimilarityBadge,
} from "@/features/suggestions/components/SimilarityBadge";

type DuplicateRuleCardProps = {
  candidate: SuggestionDuplicateCandidate;
  onViewRule?: (candidate: SuggestionDuplicateCandidate) => void;
  onCompareRule?: (candidate: SuggestionDuplicateCandidate) => void;
};

function toTitleCase(value: string) {
  if (!value) {
    return "-";
  }
  return value
    .split("_")
    .join(" ")
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}

function normalizeAction(candidate: SuggestionDuplicateCandidate) {
  const raw = String(candidate.action ?? "").trim().toLowerCase();
  if (raw) {
    return raw;
  }
  return "mask";
}

function normalizeScope(candidate: SuggestionDuplicateCandidate) {
  const raw = String(candidate.scope ?? "").trim().toLowerCase();
  if (raw) {
    return raw;
  }
  return "prompt";
}

function buildSummary(candidate: SuggestionDuplicateCandidate) {
  const summary = String(candidate.summary ?? "").trim();
  if (summary) {
    return summary;
  }
  const action = normalizeAction(candidate);
  const scope = normalizeScope(candidate);
  return `Potential overlap with an existing ${scope} rule that may ${action} similar content.`;
}

export function DuplicateRuleCard({
  candidate,
  onViewRule,
  onCompareRule,
}: DuplicateRuleCardProps) {
  const action = normalizeAction(candidate);
  const scope = normalizeScope(candidate);
  const summary = buildSummary(candidate);
  const similarityMeta = getSimilarityMeta(candidate.similarity);
  const matchLevelText =
    typeof similarityMeta.percent === "number"
      ? `Match level: ${similarityMeta.label} (${similarityMeta.percent}%)`
      : `Match level: ${similarityMeta.label}`;

  return (
    <Card className="space-y-3 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold">{candidate.name || "Unnamed rule"}</p>
          <div className="mt-1 flex items-center gap-2">
            <Badge className="bg-muted text-muted-foreground">Action: {toTitleCase(action)}</Badge>
            <Badge className="bg-muted text-muted-foreground">Scope: {toTitleCase(scope)}</Badge>
          </div>
        </div>
        <SimilarityBadge similarity={candidate.similarity} />
      </div>

      <p className="text-xs text-muted-foreground">{matchLevelText}</p>
      <p className="text-sm text-muted-foreground">{summary}</p>

      <div className="flex flex-wrap gap-2">
        <Button
          onClick={() => onViewRule?.(candidate)}
          size="sm"
          type="button"
          variant="outline"
        >
          View rule
        </Button>
        <Button
          onClick={() => onCompareRule?.(candidate)}
          size="sm"
          type="button"
        >
          Compare
        </Button>
      </div>
    </Card>
  );
}
