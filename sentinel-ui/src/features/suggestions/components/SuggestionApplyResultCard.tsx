import { Card } from "@/shared/ui/card";

type SuggestionApplyResultCardProps = {
  appliedResultJson: Record<string, unknown>;
};

function rowValue(value: unknown) {
  if (Array.isArray(value)) {
    return JSON.stringify(value);
  }
  if (typeof value === "object" && value !== null) {
    return JSON.stringify(value);
  }
  return String(value ?? "-");
}

export function SuggestionApplyResultCard({ appliedResultJson }: SuggestionApplyResultCardProps) {
  const keys = ["rule_id", "stable_key", "name", "action", "origin", "context_term_ids"];

  return (
    <Card className="space-y-3 border bg-muted/20 p-3">
      <p className="text-sm font-semibold">Apply result</p>
      <div className="grid gap-3 md:grid-cols-2">
        {keys.map((key) => (
          <div className="rounded-md border bg-background p-3" key={key}>
            <p className="text-xs text-muted-foreground">{key}</p>
            <p className="mt-1 break-all text-sm font-medium">{rowValue(appliedResultJson[key])}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}
