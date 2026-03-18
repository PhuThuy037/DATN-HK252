import { Badge } from "@/shared/ui/badge";

type SimilarityBadgeProps = {
  similarity?: number | null;
};

type SimilarityMeta = {
  label: string;
  className: string;
  percent?: number | null;
};

export function getSimilarityMeta(similarity?: number | null): SimilarityMeta {
  if (typeof similarity !== "number" || Number.isNaN(similarity)) {
    return {
      label: "Unknown similarity",
      className: "bg-muted text-muted-foreground",
      percent: null,
    };
  }

  const percent = Math.max(0, Math.min(100, Math.round(similarity * 100)));

  if (similarity > 0.9) {
    return {
      label: "Very similar",
      className: "bg-red-100 text-red-800",
      percent,
    };
  }

  if (similarity > 0.75) {
    return {
      label: "Similar",
      className: "bg-amber-100 text-amber-800",
      percent,
    };
  }

  return {
    label: "Low similarity",
    className: "bg-emerald-100 text-emerald-800",
    percent,
  };
}

export function SimilarityBadge({ similarity }: SimilarityBadgeProps) {
  const level = getSimilarityMeta(similarity);
  return <Badge className={level.className}>{level.label}</Badge>;
}
