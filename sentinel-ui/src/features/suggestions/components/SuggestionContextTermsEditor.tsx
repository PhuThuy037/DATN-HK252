import { useEffect, useMemo, useRef, useState } from "react";
import type { SuggestionContextTerm } from "@/features/suggestions/types";
import {
  contextTermsToTextareaValue,
  parseLinkedContextTermsText,
} from "@/features/rules/components/contextTermsText";
import { FieldHelpText } from "@/shared/ui/field-help-text";
import { Label } from "@/shared/ui/label";
import { StatusBadge } from "@/shared/ui/status-badge";
import { Textarea } from "@/shared/ui/textarea";

type SuggestionContextTermsEditorProps = {
  terms: SuggestionContextTerm[];
  readOnly?: boolean;
  onChange: (nextTerms: SuggestionContextTerm[]) => void;
};

function toKey(term: SuggestionContextTerm) {
  return `${String(term.entity_type ?? "").trim().toLowerCase()}::${String(term.term ?? "")
    .trim()
    .toLowerCase()}`;
}

export function SuggestionContextTermsEditor({
  terms,
  readOnly = false,
  onChange,
}: SuggestionContextTermsEditorProps) {
  const [textValue, setTextValue] = useState<string>(() => contextTermsToTextareaValue(terms));
  const isLocalTypingRef = useRef(false);

  useEffect(() => {
    if (isLocalTypingRef.current) {
      isLocalTypingRef.current = false;
      return;
    }
    setTextValue(contextTermsToTextareaValue(terms));
  }, [terms]);

  const parsedPreview = useMemo(
    () =>
      parseLinkedContextTermsText(textValue, {
        existingTerms: terms,
        defaultEntityType: "SEM_TOPIC",
      }) as SuggestionContextTerm[],
    [terms, textValue]
  );

  const metadataCount = useMemo(() => {
    const parsedSet = new Set(parsedPreview.map(toKey));
    let count = 0;
    for (const row of terms) {
      if (parsedSet.has(toKey(row))) {
        count += 1;
      }
    }
    return count;
  }, [parsedPreview, terms]);

  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label htmlFor="suggestion-linked-context-terms">Linked context terms</Label>
        <Textarea
          className="min-h-[120px]"
          disabled={readOnly}
          id="suggestion-linked-context-terms"
          onChange={(event) => {
            const nextText = event.target.value;
            setTextValue(nextText);
            isLocalTypingRef.current = true;
            const nextTerms = parseLinkedContextTermsText(nextText, {
              existingTerms: terms,
              defaultEntityType: "SEM_TOPIC",
            }) as SuggestionContextTerm[];
            onChange(nextTerms);
          }}
          placeholder="Add one term per line"
          value={textValue}
        />
        <FieldHelpText>
          Add one term per line. This mirrors the create-rule form so suggestion review matches the final rule mental model.
        </FieldHelpText>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge label={`${parsedPreview.length} linked term${parsedPreview.length === 1 ? "" : "s"}`} tone="muted" />
        {metadataCount > 0 ? (
          <StatusBadge
            label={`Reused ${metadataCount} term metadata`}
            tone="primary"
          />
        ) : null}
      </div>

      <details className="rounded-xl border border-border/80 bg-muted/10 p-3">
        <summary className="cursor-pointer text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Advanced linked context terms
        </summary>
        <div className="mt-3 space-y-2 text-xs text-muted-foreground">
          <p>Entity type, language, and weighting are preserved from existing terms when possible.</p>
          <p>New lines default to `SEM_TOPIC`, `vi`, weight `1`, window `60/20`, enabled `true`.</p>
        </div>
      </details>
    </div>
  );
}
