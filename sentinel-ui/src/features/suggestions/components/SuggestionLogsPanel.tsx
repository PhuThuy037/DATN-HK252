import type { RuleSuggestionLogOut } from "@/features/suggestions/types";
import { SuggestionLogs } from "@/features/suggestions/components/SuggestionLogs";

type SuggestionLogsPanelProps = {
  logs: RuleSuggestionLogOut[];
  isLoading: boolean;
  isError: boolean;
  errorMessage?: string;
};

export function SuggestionLogsPanel({
  logs,
  isLoading,
  isError,
  errorMessage,
}: SuggestionLogsPanelProps) {
  return (
    <SuggestionLogs
      errorMessage={errorMessage}
      isError={isError}
      isLoading={isLoading}
      logs={logs}
    />
  );
}
