import { Plus, Trash2 } from "lucide-react";
import type { SuggestionContextTerm } from "@/features/suggestions/types";
import { AppButton } from "@/shared/ui/app-button";
import { EmptyState } from "@/shared/ui/empty-state";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { StatusBadge } from "@/shared/ui/status-badge";

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

function toTitleCase(value: string) {
  return value
    .trim()
    .toLowerCase()
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
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
    <div className="space-y-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="space-y-1">
          <h4 className="text-sm font-semibold text-foreground">Context terms</h4>
          <p className="text-sm text-muted-foreground">
            Keywords work best when they are specific, easy to scan, and grouped by entity type.
          </p>
        </div>
        <AppButton
          disabled={readOnly}
          leadingIcon={<Plus className="h-3.5 w-3.5" />}
          onClick={addTerm}
          size="sm"
          type="button"
          variant="secondary"
        >
          Add term
        </AppButton>
      </div>

      {terms.length === 0 ? (
        <EmptyState
          description="Add focused keywords to improve rule matching and retrieval."
          title="No context terms yet"
        />
      ) : null}

      <div className="space-y-4">
        {Object.entries(groups).map(([entityType, groupTerms]) => {
          const groupHasDuplicates = groupTerms.some(({ term }) =>
            duplicateKeys.has(`${normalize(term.entity_type)}::${normalize(term.term)}`)
          );

          return (
            <div className="rounded-xl border border-border/80 bg-background p-4" key={entityType}>
              <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div className="flex flex-wrap items-center gap-2">
                  <h5 className="text-sm font-semibold text-foreground">{toTitleCase(entityType)}</h5>
                  <StatusBadge label={`${groupTerms.length} term${groupTerms.length === 1 ? "" : "s"}`} tone="muted" />
                  {groupHasDuplicates ? <StatusBadge label="Duplicate keyword" tone="warning" /> : null}
                </div>
                <p className="text-xs text-muted-foreground">
                  Group keywords that support the same detection intent.
                </p>
              </div>

              <div className="mt-4 grid gap-3">
                {groupTerms.map(({ index, term }) => {
                  const isDuplicate = duplicateKeys.has(
                    `${normalize(term.entity_type)}::${normalize(term.term)}`
                  );

                  return (
                    <div
                      className="space-y-4 rounded-xl border border-border/80 bg-muted/10 p-4"
                      key={index}
                    >
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div className="space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <StatusBadge label={toTitleCase(term.entity_type || "Entity type")} tone="primary" />
                            <StatusBadge status={term.enabled ? "enabled" : "disabled"} />
                            {isDuplicate ? <StatusBadge label="Duplicate" tone="warning" /> : null}
                          </div>
                          <div className="rounded-xl border border-primary/15 bg-primary/5 px-3 py-2">
                            <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                              Keyword
                            </p>
                            <p className="mt-1 break-all font-mono text-sm text-foreground">
                              {term.term?.trim() || "Enter a keyword"}
                            </p>
                          </div>
                        </div>

                        <AppButton
                          disabled={readOnly}
                          leadingIcon={<Trash2 className="h-3.5 w-3.5" />}
                          onClick={() => removeTerm(index)}
                          size="sm"
                          type="button"
                          variant="secondary"
                        >
                          Remove
                        </AppButton>
                      </div>

                      <div className="grid gap-4 md:grid-cols-2">
                        <InputField
                          disabled={readOnly}
                          helper="Entity family used to group and interpret this keyword."
                          label="Entity type"
                          onChange={(value) => updateTerm(index, "entity_type", value)}
                          value={term.entity_type}
                        />
                        <InputField
                          disabled={readOnly}
                          helper="The actual keyword or phrase that should stand out during review."
                          label="Keyword"
                          onChange={(value) => updateTerm(index, "term", value)}
                          value={term.term}
                        />
                      </div>

                      <details className="rounded-xl border border-border/80 bg-background p-3">
                        <summary className="cursor-pointer text-xs font-medium uppercase tracking-wide text-muted-foreground">
                          Advanced settings
                        </summary>
                        <div className="mt-3 grid gap-4 md:grid-cols-2">
                          <InputField
                            disabled={readOnly}
                            helper="Language used for the keyword."
                            label="Language"
                            onChange={(value) => updateTerm(index, "lang", value)}
                            value={term.lang}
                          />
                        </div>
                        <div className="mt-4 grid gap-4 md:grid-cols-3">
                          <InputField
                            disabled={readOnly}
                            helper="Relative influence of this term."
                            label="Weight"
                            onChange={(value) => updateTerm(index, "weight", toNumber(value, 1))}
                            type="number"
                            value={term.weight}
                          />
                          <InputField
                            disabled={readOnly}
                            helper="Primary token window."
                            label="Window 1"
                            onChange={(value) => updateTerm(index, "window_1", toNumber(value, 60))}
                            type="number"
                            value={term.window_1}
                          />
                          <InputField
                            disabled={readOnly}
                            helper="Secondary token window."
                            label="Window 2"
                            onChange={(value) => updateTerm(index, "window_2", toNumber(value, 20))}
                            type="number"
                            value={term.window_2}
                          />
                        </div>
                      </details>

                      {isDuplicate ? (
                        <p className="text-xs text-warning">
                          This keyword appears more than once within the same entity type.
                        </p>
                      ) : null}
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
  helper,
  value,
  onChange,
  type = "text",
  disabled = false,
}: {
  label: string;
  helper?: string;
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
      {helper ? <p className="text-xs text-muted-foreground">{helper}</p> : null}
    </div>
  );
}
