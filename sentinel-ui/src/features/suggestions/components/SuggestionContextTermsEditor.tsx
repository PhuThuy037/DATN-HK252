import { Plus, Trash2 } from "lucide-react";
import type { SuggestionContextTerm } from "@/features/suggestions/types";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";

type SuggestionContextTermsEditorProps = {
  terms: SuggestionContextTerm[];
  readOnly?: boolean;
  onChange: (nextTerms: SuggestionContextTerm[]) => void;
};

const emptyTerm: SuggestionContextTerm = {
  entity_type: "",
  term: "",
  lang: "vi",
  weight: 1,
  window_1: 60,
  window_2: 20,
  enabled: true,
};

function normalize(value: string) {
  return value.trim().toLowerCase();
}

function detectDuplicateTerms(terms: SuggestionContextTerm[]) {
  const duplicates = new Set<string>();
  const seen = new Map<string, number>();

  terms.forEach((term) => {
    const key = `${normalize(term.entity_type)}::${normalize(term.term)}`;
    if (!term.entity_type.trim() || !term.term.trim()) {
      return;
    }

    const count = seen.get(key) ?? 0;
    seen.set(key, count + 1);
    if (count >= 1) {
      duplicates.add(key);
    }
  });

  return duplicates;
}

function toNumber(value: string, fallback = 0) {
  const parsed = Number(value);
  return Number.isNaN(parsed) ? fallback : parsed;
}

export function SuggestionContextTermsEditor({
  terms,
  readOnly = false,
  onChange,
}: SuggestionContextTermsEditorProps) {
  const groups = terms.reduce<Record<string, Array<{ index: number; term: SuggestionContextTerm }>>>(
    (acc, term, index) => {
      const key = term.entity_type?.trim() || "Ungrouped";
      if (!acc[key]) {
        acc[key] = [];
      }
      acc[key].push({ index, term });
      return acc;
    },
    {}
  );

  const duplicateKeys = detectDuplicateTerms(terms);

  const updateTerm = <K extends keyof SuggestionContextTerm>(
    index: number,
    field: K,
    value: SuggestionContextTerm[K]
  ) => {
    const nextTerms = terms.map((term, termIndex) =>
      termIndex === index
        ? {
            ...term,
            [field]: value,
          }
        : term
    );

    onChange(nextTerms);
  };

  const removeTerm = (index: number) => {
    onChange(terms.filter((_, termIndex) => termIndex !== index));
  };

  const addTerm = () => {
    onChange([...terms, { ...emptyTerm }]);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h4 className="text-sm font-semibold">Context terms</h4>
          <p className="text-xs text-muted-foreground">
            Keep the business-facing fields simple here. Language and scoring parameters live in
            Advanced settings.
          </p>
        </div>
        <Button
          disabled={readOnly}
          onClick={addTerm}
          size="sm"
          type="button"
          variant="outline"
        >
          <Plus className="mr-1 h-3.5 w-3.5" />
          Add term
        </Button>
      </div>

      {terms.length === 0 && (
        <p className="text-sm text-muted-foreground">No context terms.</p>
      )}

      <div className="space-y-4">
        {Object.entries(groups).map(([entityType, groupTerms]) => {
          const groupHasDuplicates = groupTerms.some(({ term }) =>
            duplicateKeys.has(`${normalize(term.entity_type)}::${normalize(term.term)}`)
          );

          return (
            <div className="rounded-md border p-3" key={entityType}>
              <div className="flex items-center justify-between gap-2">
                <h5 className="text-sm font-medium">{entityType}</h5>
                <span className="text-xs text-muted-foreground">{groupTerms.length} term(s)</span>
              </div>

              {groupHasDuplicates && (
                <p className="mt-1 text-xs text-amber-700">Possible duplicate terms detected in this group.</p>
              )}

              <div className="mt-3 space-y-3">
                {groupTerms.map(({ index, term }) => {
                  const isDuplicate = duplicateKeys.has(
                    `${normalize(term.entity_type)}::${normalize(term.term)}`
                  );

                  return (
                    <div className="rounded-md border p-3" key={index}>
                      <div className="grid gap-3 md:grid-cols-2">
                        <InputField
                          disabled={readOnly}
                          label="Entity type"
                          onChange={(value) => updateTerm(index, "entity_type", value)}
                          value={term.entity_type}
                        />
                        <InputField
                          disabled={readOnly}
                          label="Term"
                          onChange={(value) => updateTerm(index, "term", value)}
                          value={term.term}
                        />
                      </div>

                      <details className="mt-3 rounded-md border bg-muted/20 p-2">
                        <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
                          Advanced settings
                        </summary>
                        <div className="mt-2 grid gap-3 md:grid-cols-2">
                          <InputField
                            disabled={readOnly}
                            label="Language"
                            onChange={(value) => updateTerm(index, "lang", value)}
                            value={term.lang}
                          />
                        </div>
                        <div className="mt-3 grid gap-3 md:grid-cols-3">
                          <InputField
                            disabled={readOnly}
                            label="Weight"
                            onChange={(value) => updateTerm(index, "weight", toNumber(value, 1))}
                            type="number"
                            value={term.weight}
                          />
                          <InputField
                            disabled={readOnly}
                            label="Window 1"
                            onChange={(value) => updateTerm(index, "window_1", toNumber(value, 60))}
                            type="number"
                            value={term.window_1}
                          />
                          <InputField
                            disabled={readOnly}
                            label="Window 2"
                            onChange={(value) => updateTerm(index, "window_2", toNumber(value, 20))}
                            type="number"
                            value={term.window_2}
                          />
                        </div>
                      </details>

                      <div className="mt-3 flex items-center justify-between gap-2">
                        <label className="inline-flex items-center gap-2 text-sm">
                          <input
                            checked={term.enabled}
                            disabled={readOnly}
                            onChange={(event) => updateTerm(index, "enabled", event.target.checked)}
                            type="checkbox"
                          />
                          <span>{term.enabled ? "Enabled" : "Disabled"}</span>
                        </label>

                        <Button
                          disabled={readOnly}
                          onClick={() => removeTerm(index)}
                          size="sm"
                          type="button"
                          variant="outline"
                        >
                          <Trash2 className="mr-1 h-3.5 w-3.5" />
                          Remove
                        </Button>
                      </div>

                      {isDuplicate && (
                        <p className="mt-2 text-xs text-amber-700">
                          This term looks duplicated within the same entity type.
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function InputField({
  label,
  value,
  onChange,
  type = "text",
  disabled = false,
}: {
  label: string;
  value: string | number;
  onChange: (value: string) => void;
  type?: string;
  disabled?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Input
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        type={type}
        value={value}
      />
    </div>
  );
}
