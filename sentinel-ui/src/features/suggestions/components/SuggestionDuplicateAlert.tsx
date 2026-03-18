import { useEffect, useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import type { SuggestionDuplicateCandidate } from "@/features/suggestions/types";
import { Button } from "@/shared/ui/button";
import { DuplicateList } from "@/features/suggestions/components/DuplicateList";
import { Card } from "@/shared/ui/card";

type DuplicateInsight = {
  level?: "none" | "weak" | "strong";
  reason?: string;
  duplicateRisk?: string;
  conflictRisk?: string;
  runtimeUsable?: boolean;
  rationale?: string;
  similarRules?: SuggestionDuplicateCandidate[];
  candidates?: SuggestionDuplicateCandidate[];
};

type SuggestionDuplicateAlertProps = {
  insight?: DuplicateInsight | null;
  onViewRule?: (candidate: SuggestionDuplicateCandidate) => void;
  onCompareRule?: (candidate: SuggestionDuplicateCandidate) => void;
  forceExpand?: boolean;
};

export function SuggestionDuplicateAlert({
  insight,
  onViewRule,
  onCompareRule,
  forceExpand = false,
}: SuggestionDuplicateAlertProps) {
  if (!insight) {
    return null;
  }

  const candidates = insight.similarRules ?? insight.candidates ?? [];
  const level =
    insight.level ?? (candidates.length > 0 ? "strong" : "none");
  if (level === "none") {
    return null;
  }
  const warning = level === "strong";
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (forceExpand && warning && candidates.length > 0) {
      setExpanded(true);
    }
  }, [forceExpand, warning, candidates.length]);

  const summaryText = useMemo(() => {
    if (warning) {
      return `${candidates.length} similar rule${candidates.length > 1 ? "s" : ""} found. Review before continuing.`;
    }
    return "Weak semantic overlap detected. No strong similar rules were found.";
  }, [warning, candidates.length]);

  const titleText = warning
    ? "Possible duplicate detected"
    : "Potential duplicate signal";
  const reasonText = insight.reason ?? insight.rationale;
  const cardClass = warning
    ? "border-amber-300 bg-amber-50 p-3"
    : "border-amber-200 bg-amber-50/50 p-3";

  return (
    <Card className={cardClass}>
      <div className="flex items-start gap-2">
        {warning && <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-700" />}
        <div className="space-y-1">
          <p className="text-sm font-semibold">{titleText}</p>
          <p className="text-xs text-muted-foreground">{summaryText}</p>
          {reasonText && <p className="text-xs text-muted-foreground">{reasonText}</p>}
        </div>
      </div>

      {warning && candidates.length > 0 && (
        <div className="mt-3 space-y-3">
          <Button
            onClick={() => setExpanded((current) => !current)}
            size="sm"
            type="button"
            variant="outline"
          >
            {expanded ? "Hide similar rules" : "View similar rules"}
          </Button>

          {expanded && (
            <DuplicateList
              candidates={candidates}
              onCompareRule={onCompareRule}
              onViewRule={onViewRule}
            />
          )}
        </div>
      )}
    </Card>
  );
}
