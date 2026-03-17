import { Trash2 } from "lucide-react";
import { getPolicyErrorMessage } from "@/features/policies/api/policiesApi";
import {
  useDeletePolicyDocument,
  usePolicyDocuments,
  useTogglePolicyDocumentEnabled,
} from "@/features/policies/hooks";
import { formatPolicyDate } from "@/features/policies/components/PolicyStatusBadge";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { toast } from "@/shared/ui/use-toast";

type PolicyDocumentsTabProps = {
  ruleSetId: string;
};

export function PolicyDocumentsTab({ ruleSetId }: PolicyDocumentsTabProps) {
  const documentsQuery = usePolicyDocuments(ruleSetId);
  const toggleMutation = useTogglePolicyDocumentEnabled(ruleSetId);
  const deleteMutation = useDeletePolicyDocument(ruleSetId);

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

  const handleDelete = async (documentId: string) => {
    const confirmed = window.confirm("Delete this policy document?");
    if (!confirmed) {
      return;
    }

    try {
      await deleteMutation.mutateAsync(documentId);
      toast({
        title: "Document deleted",
        description: "Policy document was soft deleted.",
        variant: "success",
      });
    } catch (error) {
      toast({
        title: "Delete failed",
        description: getPolicyErrorMessage(error, "Unable to delete document"),
        variant: "destructive",
      });
    }
  };

  if (documentsQuery.isLoading) {
    return <Card className="p-4 text-sm text-muted-foreground">Loading policy documents...</Card>;
  }

  if (documentsQuery.isError) {
    return (
      <Card className="p-4 text-sm text-destructive">
        {getPolicyErrorMessage(documentsQuery.error, "Failed to load policy documents")}
      </Card>
    );
  }

  const documents = documentsQuery.data ?? [];

  if (documents.length === 0) {
    return (
      <Card className="p-6 text-center">
        <p className="text-sm font-medium">No policy documents</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Create an ingest job to add policy documents.
        </p>
      </Card>
    );
  }

  return (
    <Card className="p-0">
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
            {documents.map((doc) => {
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
                    <label className="inline-flex cursor-pointer items-center gap-2 text-xs">
                      <input
                        checked={doc.enabled}
                        disabled={toggleMutation.isPending || !isEditable}
                        onChange={(event) => {
                          void handleToggle(doc.id, event.target.checked);
                        }}
                        type="checkbox"
                      />
                      {doc.enabled ? "Enabled" : "Disabled"}
                    </label>
                  </td>
                  <td className="px-3 py-2">
                    <Button
                      disabled={deleteMutation.isPending || !isEditable}
                      onClick={() => {
                        void handleDelete(doc.id);
                      }}
                      size="sm"
                      type="button"
                      variant="outline"
                    >
                      <Trash2 className="mr-1 h-3.5 w-3.5" />
                      Delete
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </ScrollArea>
    </Card>
  );
}
