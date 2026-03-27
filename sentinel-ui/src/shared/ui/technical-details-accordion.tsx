import type { ReactNode } from "react";
import { cn } from "@/shared/lib/utils";
import { appCodeBlockClassName } from "@/shared/ui/design-tokens";

export type TechnicalDetailsSection = {
  title: ReactNode;
  description?: ReactNode;
  content?: ReactNode;
  data?: unknown;
  defaultOpen?: boolean;
  emptyMessage?: string;
};

type TechnicalDetailsAccordionProps = {
  title?: ReactNode;
  description?: ReactNode;
  sections?: TechnicalDetailsSection[];
  defaultOpen?: boolean;
  className?: string;
};

function formatJson(value: unknown) {
  if (typeof value === "string") {
    return value;
  }

  try {
    return JSON.stringify(value ?? null, null, 2);
  } catch {
    return String(value);
  }
}

export function TechnicalDetailsAccordion({
  title = "Technical details",
  description,
  sections = [],
  defaultOpen = false,
  className,
}: TechnicalDetailsAccordionProps) {
  return (
    <details className={cn("rounded-xl border border-border/80 bg-muted/20 p-3", className)} open={defaultOpen}>
      <summary className="cursor-pointer list-none text-sm font-semibold text-foreground">
        {title}
      </summary>
      {description ? <p className="mt-2 text-xs text-muted-foreground">{description}</p> : null}

      <div className="mt-3 space-y-3">
        {sections.map((section, index) => (
          <details className="rounded-lg border border-border/80 bg-background p-3 text-xs" key={index} open={section.defaultOpen}>
            <summary className="cursor-pointer list-none font-medium text-muted-foreground">
              {section.title}
            </summary>
            {section.description ? <p className="mt-2 text-xs text-muted-foreground">{section.description}</p> : null}
            {section.content ? (
              <div className="mt-2">{section.content}</div>
            ) : (
              <pre className={cn("mt-2", appCodeBlockClassName)}>
                {formatJson(section.data ?? section.emptyMessage ?? null)}
              </pre>
            )}
          </details>
        ))}
      </div>
    </details>
  );
}
