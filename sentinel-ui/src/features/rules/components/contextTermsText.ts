export type ContextTermTextItem = {
  entity_type: string;
  term: string;
  lang: string;
  weight: number;
  window_1: number;
  window_2: number;
  enabled: boolean;
};

type ParseLinkedContextTermsOptions = {
  existingTerms?: ContextTermTextItem[] | null;
  defaultEntityType?: string;
  defaultLang?: string;
  defaultWeight?: number;
  defaultWindow1?: number;
  defaultWindow2?: number;
  defaultEnabled?: boolean;
};

function normalizeTerm(value: string) {
  return String(value ?? "").trim().toLowerCase();
}

export function contextTermsToTextareaValue(
  contextTerms: ContextTermTextItem[] | null | undefined
): string {
  const seen = new Set<string>();
  const lines: string[] = [];

  for (const row of contextTerms ?? []) {
    const value = String(row.term ?? "").trim();
    if (!value) {
      continue;
    }
    const normalized = normalizeTerm(value);
    if (seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    lines.push(value);
  }

  return lines.join("\n");
}

export function parseLinkedContextTermsText(
  value: string,
  options: ParseLinkedContextTermsOptions = {}
): ContextTermTextItem[] {
  const seen = new Set<string>();
  const out: ContextTermTextItem[] = [];
  const existingMap = new Map<string, ContextTermTextItem>();
  for (const row of options.existingTerms ?? []) {
    const normalized = normalizeTerm(row.term);
    if (!normalized || existingMap.has(normalized)) {
      continue;
    }
    existingMap.set(normalized, row);
  }

  const defaultEntityType = String(options.defaultEntityType ?? "SEM_TOPIC").trim() || "SEM_TOPIC";
  const defaultLang = String(options.defaultLang ?? "vi").trim() || "vi";
  const defaultWeight =
    typeof options.defaultWeight === "number" && Number.isFinite(options.defaultWeight)
      ? options.defaultWeight
      : 1;
  const defaultWindow1 =
    typeof options.defaultWindow1 === "number" && Number.isFinite(options.defaultWindow1)
      ? Math.max(0, Math.trunc(options.defaultWindow1))
      : 60;
  const defaultWindow2 =
    typeof options.defaultWindow2 === "number" && Number.isFinite(options.defaultWindow2)
      ? Math.max(0, Math.trunc(options.defaultWindow2))
      : 20;
  const defaultEnabled = options.defaultEnabled ?? true;

  for (const rawLine of String(value ?? "").split("\n")) {
    const term = rawLine.trim();
    if (!term) {
      continue;
    }
    const normalized = normalizeTerm(term);
    if (seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);

    const existing = existingMap.get(normalized);
    if (existing) {
      out.push({
        entity_type: String(existing.entity_type ?? defaultEntityType) || defaultEntityType,
        term,
        lang: String(existing.lang ?? defaultLang) || defaultLang,
        weight:
          typeof existing.weight === "number" && Number.isFinite(existing.weight)
            ? existing.weight
            : defaultWeight,
        window_1:
          typeof existing.window_1 === "number" && Number.isFinite(existing.window_1)
            ? Math.max(0, Math.trunc(existing.window_1))
            : defaultWindow1,
        window_2:
          typeof existing.window_2 === "number" && Number.isFinite(existing.window_2)
            ? Math.max(0, Math.trunc(existing.window_2))
            : defaultWindow2,
        enabled: typeof existing.enabled === "boolean" ? existing.enabled : defaultEnabled,
      });
      continue;
    }

    out.push({
      entity_type: defaultEntityType,
      term,
      lang: defaultLang,
      weight: defaultWeight,
      window_1: defaultWindow1,
      window_2: defaultWindow2,
      enabled: defaultEnabled,
    });
  }

  return out;
}
