import { useMutation } from "@tanstack/react-query";
import { debugEvaluateText } from "@/features/rules/api/rulesApi";
import type { DebugEvaluateRequest } from "@/features/rules/types";

export function useDebugEvaluate() {
  return useMutation({
    mutationKey: ["rule-debug-evaluate"],
    mutationFn: (payload: DebugEvaluateRequest) => debugEvaluateText(payload),
  });
}
