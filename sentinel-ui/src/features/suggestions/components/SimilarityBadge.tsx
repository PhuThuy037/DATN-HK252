import { StatusBadge } from "@/shared/ui/status-badge";

type SimilarityBadgeProps = {
  similarity?: number | null;
};

type SimilarityMeta = {
  label: string;
  tone: "success" | "warning" | "danger" | "muted";
  percent?: number | null;
};

export function getSimilarityMeta(similarity?: number | null): SimilarityMeta {
  if (typeof similarity !== "number" || Number.isNaN(similarity)) {
    return {
      label: "Unknown similarity",
      tone: "muted",
      percent: null,
    };
  }

  const percent = Math.max(0, Math.min(100, Math.round(similarity * 100)));

  if (similarity >= 0.99) {
    return {
      label: "Exact duplicate",
      tone: "danger",
      percent,
    };
  }

  if (similarity > 0.9) {
    return {
      label: "Very similar",
      tone: "danger",
      percent,
    };
  }

  if (similarity > 0.75) {
    return {
      label: "Similar",
      tone: "warning",
      percent,
    };
  }

  return {
    label: "Low similarity",
    tone: "success",
    percent,
  };
}

export function SimilarityBadge({ similarity }: SimilarityBadgeProps) {
  const level = getSimilarityMeta(similarity);
  const label =
    typeof level.percent === "number" ? `${level.label} (${level.percent}%)` : level.label;

  return <StatusBadge label={label} tone={level.tone} />;
}
