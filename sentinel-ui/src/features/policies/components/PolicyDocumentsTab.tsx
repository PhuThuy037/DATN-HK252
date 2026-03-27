import { useState } from "react";
import { Trash2 } from "lucide-react";
import { getPolicyErrorMessage } from "@/features/policies/api/policiesApi";
import {
  useDeletePolicyDocument,
  usePolicyDocuments,
  useTogglePolicyDocumentEnabled,
} from "@/features/policies/hooks";
import { formatPolicyDate } from "@/features/policies/components/PolicyStatusBadge";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppButton } from "@/shared/ui/app-button";
import { AppLoadingState } from "@/shared/ui/app-loading-state";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";
import { EmptyState } from "@/shared/ui/empty-state";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { StatusBadge } from "@/shared/ui/status-badge";
import { toast } from "@/shared/ui/use-toast";

type PolicyDocumentsTabProps = {
  ruleSetId: string;
};

export function PolicyDocumentsTab({ ruleSetId }: PolicyDocumentsTabProps) {
  const documentsQuery = usePolicyDocuments(ruleSetId);
  const toggleMutation = useTogglePolicyDocumentEnabled(ruleSetId);
  const deleteMutation = useDeletePolicyDocument(ruleSetId);
  const [documentPendingDelete, setDocumentPendingDelete] = useState<{
    id: string;
    title: string;
  } | null>(null);

  const handleToggle = async (documentId: string, enabled: boolean) => {
    try {
      await toggleMutation.mutateAsync({
        documentId,
        payload: { enabled },
      });
      toast({
        title: "Document updated",
        description: `Document is now ${enabled ? "enabled" : "disabled"}.`,
        variant: "success",
      });
    } catch (error) {
      toast({
        title: "Update failed",
        description: getPolicyErrorMessage(error, "Unable to update document"),
        variant: "destructive",
      });
    }
  };

  const handleDelete = async () => {
    if (!documentPendingDelete) {
      return;
    }

    try {
      await deleteMutation.mutateAsync(documentPendingDelete.id);
      toast({
        title: "Document deleted",
        description: "Policy document removed from this workspace.",
        variant: "success",
      });
      setDocumentPendingDelete(null);
    } catch (error) {
      toast({
        title: "Delete failed",
        description: getPolicyErrorMessage(error, "Unable to delete document"),
        variant: "destructive",
      });
    }
  };

  if (documentsQuery.isLoading) {
    return (
      <AppLoadingState
        compact
        description="Loading policy documents for this rule set."
        title="Loading documents"
      />
    );
  }

  if (documentsQuery.isError) {
    return (
      <AppAlert
        description={getPolicyErrorMessage(documentsQuery.error, "Failed to load policy documents")}
        title="Unable to load policy documents"
        variant="error"
      />
    );
  }

  const documents = documentsQuery.data ?? [];

  const visibleDocuments = documentPendingDelete
    ? documents.filter((doc) => doc.id !== documentPendingDelete.id)
    : documents;

  if (visibleDocuments.length === 0) {
    return (
      <EmptyState
        description="Run an ingest job to add policy documents to this workspace."
        title="No documents yet"
      />
    );
  }

  return (
    <>
      <AppSectionCard className="p-0" contentClassName="space-y-0">
        <ScrollArea className="max-h-[60vh]">
          <table className="w-full min-w-[900px] text-sm">
          <thead className="sticky top-0 bg-muted/50 text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-3 py-2">Title</th>
              <th className="px-3 py-2">Stable key</th>
              <th className="px-3 py-2">Doc type</th>
              <th className="px-3 py-2">Version</th>
              <th className="px-3 py-2">Created</th>
              <th className="px-3 py-2">Enabled</th>
              <th className="px-3 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {visibleDocuments.map((doc) => {
              // API returns global docs too (rule_set_id=null), but update/delete are only allowed for current rule-set owned docs.
              // Keep global docs visible and mark them read-only to avoid avoidable 404 on mutable endpoints.
              const isEditable = doc.rule_set_id === ruleSetId;

              return (
                <tr className="border-t" key={doc.id}>
                  <td className="px-3 py-2 font-medium">{doc.title}</td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">
                    {doc.stable_key}
                    {!isEditable && (
                      <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase">
                        global
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2">{doc.doc_type}</td>
                  <td className="px-3 py-2">{doc.version}</td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">
                    {formatPolicyDate(doc.created_at)}
                  </td>
                  <td className="px-3 py-2">
                    <div className="inline-flex items-center gap-2">
                      <StatusBadge status={doc.enabled ? "enabled" : "disabled"} />
                      <AppButton
                        disabled={toggleMutation.isPending || !isEditable}
                        onClick={() => {
                          void handleToggle(doc.id, !doc.enabled);
                        }}
                        size="sm"
                        type="button"
                        variant="secondary"
                      >
                        {doc.enabled ? "Disable" : "Enable"}
                      </AppButton>
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <AppButton
                      disabled={deleteMutation.isPending || !isEditable}
                      onClick={() => {
                        setDocumentPendingDelete({
                          id: doc.id,
                          title: doc.title,
                        });
                      }}
                      size="sm"
                      type="button"
                      variant="secondary"
                    >
                      <Trash2 className="mr-1 h-3.5 w-3.5" />
                      Delete
                    </AppButton>
                  </td>
                </tr>
              );
            })}
          </tbody>
          </table>
        </ScrollArea>
      </AppSectionCard>

      <ConfirmDialog
        confirmLabel={deleteMutation.isPending ? "Deleting..." : "Delete document"}
        confirmVariant="danger"
        description={
          documentPendingDelete
            ? `Delete "${documentPendingDelete.title}" from this workspace? This action cannot be undone.`
            : undefined
        }
        isBusy={deleteMutation.isPending}
        onClose={() => setDocumentPendingDelete(null)}
        onConfirm={() => {
          void handleDelete();
        }}
        open={Boolean(documentPendingDelete)}
        title="Delete policy document?"
      />
    </>
  );
}
