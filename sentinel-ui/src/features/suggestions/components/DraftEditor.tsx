import { AlertTriangle } from "lucide-react";
import { Label } from "@/shared/ui/label";
import { Textarea } from "@/shared/ui/textarea";

type DraftEditorProps = {
  ruleJson: string;
  contextTermsJson: string;
  readOnly?: boolean;
  validationError?: string | null;
  onRuleJsonChange: (value: string) => void;
  onContextTermsJsonChange: (value: string) => void;
};

export function DraftEditor({
  ruleJson,
  contextTermsJson,
  readOnly = false,
  validationError,
  onRuleJsonChange,
  onContextTermsJsonChange,
}: DraftEditorProps) {
  return (
    <div className="space-y-4">
      {validationError && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 h-4 w-4" />
          <span>{validationError}</span>
        </div>
      )}

      <div className="space-y-2">
        <Label>Draft rule (JSON)</Label>
        <Textarea
          className="min-h-[220px] font-mono text-xs"
          disabled={readOnly}
          onChange={(event) => onRuleJsonChange(event.target.value)}
          value={ruleJson}
        />
      </div>

      <div className="space-y-2">
        <Label>Context terms (JSON array)</Label>
        <Textarea
          className="min-h-[180px] font-mono text-xs"
          disabled={readOnly}
          onChange={(event) => onContextTermsJsonChange(event.target.value)}
          value={contextTermsJson}
        />
      </div>

      {readOnly && (
        <p className="text-xs text-muted-foreground">
          Draft is read-only because suggestion is no longer in draft status.
        </p>
      )}
    </div>
  );
}
