import { Fragment } from "react";
import { cn } from "@/shared/lib/utils";

type HighlightedTextProps = {
  text: string;
  terms?: string[];
  className?: string;
};

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function normalizeTerms(terms?: string[]) {
  return Array.from(
    new Set(
      (terms ?? [])
        .map((term) => term.trim())
        .filter((term) => term.length >= 3)
        .sort((a, b) => b.length - a.length)
    )
  ).slice(0, 12);
}

export function HighlightedText({
  text,
  terms = [],
  className,
}: HighlightedTextProps) {
  const normalizedTerms = normalizeTerms(terms);

  if (!text || normalizedTerms.length === 0) {
    return <span className={className}>{text}</span>;
  }

  const pattern = new RegExp(`(${normalizedTerms.map(escapeRegExp).join("|")})`, "gi");
  const parts = text.split(pattern);

  return (
    <span className={className}>
      {parts.map((part, index) => {
        const isMatch = normalizedTerms.some(
          (term) => term.toLowerCase() === part.toLowerCase()
        );

        return isMatch ? (
          <mark
            className={cn(
              "rounded bg-warning-muted px-1 py-0.5 text-foreground",
              "shadow-[inset_0_0_0_1px_hsl(var(--warning-border))]"
            )}
            key={`${part}-${index}`}
          >
            {part}
          </mark>
        ) : (
          <Fragment key={`${part}-${index}`}>{part}</Fragment>
        );
      })}
    </span>
  );
}
