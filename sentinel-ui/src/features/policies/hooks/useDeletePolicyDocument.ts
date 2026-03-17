import { useMutation, useQueryClient } from "@tanstack/react-query";
import { deletePolicyDocument } from "@/features/policies/api/policiesApi";
import { policyQueryKeys } from "@/features/policies/hooks/queryKeys";

export function useDeletePolicyDocument(ruleSetId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (documentId: string) =>
      deletePolicyDocument(ruleSetId as string, documentId),
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
