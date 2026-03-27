import type { SuggestionDuplicateCandidate } from "@/features/suggestions/types";
import { AppButton } from "@/shared/ui/app-button";
import { Card } from "@/shared/ui/card";
import { HighlightedText } from "@/features/suggestions/components/HighlightedText";
import {
  getSimilarityMeta,
  SimilarityBadge,
} from "@/features/suggestions/components/SimilarityBadge";
import { StatusBadge } from "@/shared/ui/status-badge";

type DuplicateRuleCardProps = {
  candidate: SuggestionDuplicateCandidate;
  highlightTerms?: string[];
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

function getActionTone(action: string): "success" | "warning" | "danger" | "primary" {
  if (action === "allow") {
    return "success";
  }
  if (action === "mask") {
    return "warning";
  }
  if (action === "block") {
    return "danger";
  }
  return "primary";
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
  highlightTerms = [],
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
    <Card className="space-y-4 p-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-foreground">
              <HighlightedText
                terms={highlightTerms}
                text={candidate.name || "Unnamed rule"}
              />
            </h4>
            <StatusBadge label={toTitleCase(action)} tone={getActionTone(action)} />
            <StatusBadge label={toTitleCase(scope)} tone="muted" />
          </div>
          <p className="text-sm text-muted-foreground">
            <HighlightedText terms={highlightTerms} text={summary} />
          </p>
          <p className="break-all text-xs text-muted-foreground">
            <HighlightedText
              terms={highlightTerms}
              text={candidate.stable_key?.trim() || candidate.rule_id}
            />
          </p>
        </div>

        <div className="space-y-1 md:text-right">
          <SimilarityBadge similarity={candidate.similarity} />
          <p className="text-xs text-muted-foreground">{matchLevelText}</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <AppButton
          onClick={() => onViewRule?.(candidate)}
          size="sm"
          type="button"
          variant="secondary"
        >
          View rule
        </AppButton>
        <AppButton
          onClick={() => onCompareRule?.(candidate)}
          size="sm"
          type="button"
          variant="primary"
        >
          Review differences
        </AppButton>
      </div>
    </Card>
  );
}
