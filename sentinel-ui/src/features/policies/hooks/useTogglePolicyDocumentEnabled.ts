import { useMutation, useQueryClient } from "@tanstack/react-query";
import { togglePolicyDocumentEnabled } from "@/features/policies/api/policiesApi";
import { policyQueryKeys } from "@/features/policies/hooks/queryKeys";
import type { PolicyDocumentToggleEnabledPayload } from "@/features/policies/types";

type Input = {
  documentId: string;
  payload: PolicyDocumentToggleEnabledPayload;
};

export function useTogglePolicyDocumentEnabled(ruleSetId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ documentId, payload }: Input) =>
      togglePolicyDocumentEnabled(ruleSetId as string, documentId, payload),
    onSuccess: () => {
      if (!ruleSetId) {
        return;
      }
      queryClient.invalidateQueries({
        queryKey: policyQueryKeys.documents(ruleSetId),
      });
    },
  });
}
