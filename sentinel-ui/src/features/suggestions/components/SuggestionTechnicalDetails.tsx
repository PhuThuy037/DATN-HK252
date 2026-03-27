import type {
  RuleSuggestionGetOut,
  RuleSuggestionLogOut,
  SuggestionDuplicateCandidate,
} from "@/features/suggestions/types";
import { SuggestionLogsPanel } from "@/features/suggestions/components/SuggestionLogsPanel";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { TechnicalDetailsAccordion } from "@/shared/ui/technical-details-accordion";

type SuggestionTechnicalDetailsProps = {
  suggestion: RuleSuggestionGetOut;
  logs: RuleSuggestionLogOut[];
  logsLoading: boolean;
  logsError: boolean;
  logsErrorMessage?: string;
  unsavedDraftSnapshot?: string | null;
  duplicateInsight?: {
    level?: "none" | "weak" | "strong";
    reason?: string;
    duplicateRisk?: string;
    conflictRisk?: string;
    runtimeUsable?: boolean;
    rationale?: string;
    similarRules?: SuggestionDuplicateCandidate[];
    candidates?: SuggestionDuplicateCandidate[];
  } | null;
};

function formatDuplicateReason(reason?: string | null) {
  const text = String(reason ?? "").trim();
  if (!text) {
    return null;
  }

  const normalized = text.toLowerCase();
  if (normalized.includes("semantic_signature_match")) {
    return "Detected via semantic matching";
  }

  if (/^[a-z0-9_]+$/.test(normalized) || normalized.includes("_")) {
    return null;
  }

  return text;
}

export function SuggestionTechnicalDetails({
  suggestion,
  logs,
  logsLoading,
  logsError,
  logsErrorMessage,
  unsavedDraftSnapshot,
  duplicateInsight,
}: SuggestionTechnicalDetailsProps) {
  const duplicateSections =
    (Array.isArray(duplicateInsight?.similarRules) && duplicateInsight.similarRules.length > 0) ||
    (Array.isArray(duplicateInsight?.candidates) && duplicateInsight.candidates.length > 0)
      ? [
          {
            title: "Duplicate candidate technical data",
            data: {
              level: duplicateInsight?.level,
              reason: formatDuplicateReason(duplicateInsight?.reason ?? duplicateInsight?.rationale),
              similar_rules: duplicateInsight?.similarRules ?? duplicateInsight?.candidates ?? [],
            },
          },
        ]
      : [];

  const draftSections = unsavedDraftSnapshot
    ? [
        {
          title: "Unsaved local draft snapshot",
          data: unsavedDraftSnapshot,
        },
      ]
    : [];

  return (
    <AppSectionCard
      description="Engine payloads and logs stay tucked away here for deeper troubleshooting."
      title="Technical details"
    >
      <TechnicalDetailsAccordion
        description="Open this section when you need the underlying metadata or raw JSON."
        sections={[
          {
            title: "Metadata",
            content: (
              <div className="grid gap-2 text-xs text-muted-foreground md:grid-cols-2">
                <p>dedupe_key: {suggestion.dedupe_key}</p>
                <p>created_by: {suggestion.created_by}</p>
                <p>type: {suggestion.type}</p>
                <p>status: {suggestion.status}</p>
              </div>
            ),
          },
          {
            title: "Raw explanation JSON",
            data: suggestion.explanation ?? null,
          },
          {
            title: "Raw quality signals JSON",
            data: suggestion.quality_signals ?? null,
          },
          ...duplicateSections,
          ...draftSections,
        ]}
        title="Technical details"
      />

      <TechnicalDetailsAccordion
        sections={[
          {
            title: "Suggestion logs",
            content: (
              <SuggestionLogsPanel
                errorMessage={logsErrorMessage}
                isError={logsError}
                isLoading={logsLoading}
                logs={logs}
              />
            ),
          },
        ]}
        title="Logs"
      />
    </AppSectionCard>
  );
}
