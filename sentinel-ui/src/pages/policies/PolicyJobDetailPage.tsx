import { useState } from "react";
import { ArrowLeft, RotateCcw } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { getPolicyErrorMessage } from "@/features/policies/api/policiesApi";
import { PolicyStatusBadge, formatPolicyDate, shortPolicyId } from "@/features/policies/components";
import { usePolicyIngestJobDetail, useRetryPolicyIngestJob } from "@/features/policies/hooks";
import { useMyRuleSets } from "@/features/rules/hooks";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppButton } from "@/shared/ui/app-button";
import { AppLoadingState } from "@/shared/ui/app-loading-state";
import { AppPageHeader } from "@/shared/ui/app-page-header";
import { AppSectionCard } from "@/shared/ui/app-section-card";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";
import { EmptyState } from "@/shared/ui/empty-state";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { TechnicalDetailsAccordion } from "@/shared/ui/technical-details-accordion";
import { toast } from "@/shared/ui/use-toast";

export function PolicyJobDetailPage() {
  const navigate = useNavigate();
  const { jobId } = useParams();

  const myRuleSetsQuery = useMyRuleSets();
  const ruleSetId = myRuleSetsQuery.data?.[0]?.id;

  const detailQuery = usePolicyIngestJobDetail(ruleSetId, jobId);
  const retryMutation = useRetryPolicyIngestJob(ruleSetId, jobId);
  const [retryDialogOpen, setRetryDialogOpen] = useState(false);

  const handleRetry = async () => {
    if (!jobId) {
      return;
    }

    try {
      const retried = await retryMutation.mutateAsync();
      toast({
        title: "Retry job created",
        description: `New job ${shortPolicyId(retried.id)} has been queued.`,
        variant: "success",
      });
      setRetryDialogOpen(false);
      navigate(`/app/policies/jobs/${retried.id}`);
    } catch (error) {
      toast({
        title: "Retry failed",
        description: getPolicyErrorMessage(error, "Unable to retry failed items"),
        variant: "destructive",
      });
    }
  };

  if (myRuleSetsQuery.isLoading || detailQuery.isLoading) {
    return (
      <section className="p-6">
        <AppLoadingState
          className="mx-auto max-w-3xl"
          description="Loading this ingest job and its item status."
          title="Loading job detail"
        />
      </section>
    );
  }

  if (myRuleSetsQuery.isError || !ruleSetId) {
    return (
      <section className="p-6">
        <AppAlert title="Unable to resolve current rule set." variant="error" />
      </section>
    );
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <section className="p-6">
        <AppAlert
          description={getPolicyErrorMessage(detailQuery.error, "Unable to load ingest job detail")}
          title="Unable to load ingest job detail"
          variant="error"
        />
      </section>
    );
  }

  const job = detailQuery.data;
  const canRetry = job.failed_items > 0;

  return (
    <section className="h-full overflow-auto p-6">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4">
        <AppPageHeader
          actions={
            <>
              <AppButton
                onClick={() => navigate("/app/policies/jobs")}
                size="sm"
                type="button"
                variant="secondary"
              >
                <ArrowLeft className="h-4 w-4" />
                Back to jobs
              </AppButton>

              {canRetry && (
                <AppButton
                  disabled={retryMutation.isPending}
                  onClick={() => setRetryDialogOpen(true)}
                  size="sm"
                  type="button"
                >
                  <RotateCcw className="h-4 w-4" />
                  Retry failed items
                </AppButton>
              )}
            </>
          }
          meta={`Rule set ID: ${ruleSetId}`}
          subtitle="Review ingest job progress, item outcomes, and raw error payloads."
          title={`Policy job ${shortPolicyId(job.id)}`}
        />

        <AppSectionCard
          description="Start with the overall job outcome, then inspect item-level failures and raw payloads if needed."
          title="Job summary"
        >
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold">Job {shortPolicyId(job.id)}</p>
            <PolicyStatusBadge status={job.status} />
          </div>

          <div className="grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-xl border border-border/70 bg-background p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Total items</p>
              <p className="mt-1 text-base font-semibold text-foreground">{job.total_items}</p>
            </div>
            <div className="rounded-xl border border-border/70 bg-background p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Succeeded</p>
              <p className="mt-1 text-base font-semibold text-foreground">{job.success_items}</p>
            </div>
            <div className="rounded-xl border border-border/70 bg-background p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Failed</p>
              <p className="mt-1 text-base font-semibold text-foreground">{job.failed_items}</p>
            </div>
            <div className="rounded-xl border border-border/70 bg-background p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Skipped</p>
              <p className="mt-1 text-base font-semibold text-foreground">{job.skipped_items}</p>
            </div>
          </div>

          <div className="grid gap-3 text-sm md:grid-cols-2">
            <div className="rounded-xl border border-border/70 bg-muted/15 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Created</p>
              <p className="mt-1 text-foreground">{formatPolicyDate(job.created_at)}</p>
            </div>
            <div className="rounded-xl border border-border/70 bg-muted/15 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Started</p>
              <p className="mt-1 text-foreground">{formatPolicyDate(job.started_at)}</p>
            </div>
            <div className="rounded-xl border border-border/70 bg-muted/15 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Finished</p>
              <p className="mt-1 text-foreground">{formatPolicyDate(job.finished_at)}</p>
            </div>
            <div className="rounded-xl border border-border/70 bg-muted/15 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Retry of job</p>
              <p className="mt-1 text-foreground">{job.retry_of_job_id ?? "-"}</p>
            </div>
          </div>

          <TechnicalDetailsAccordion
            sections={[
              {
                title: "error_json",
                data: job.error_json ?? null,
              },
            ]}
            title="Technical details"
          />
        </AppSectionCard>

        {job.items.length === 0 ? (
          <EmptyState
            description="This job has no line items yet."
            title="No job items"
          />
        ) : (
          <AppSectionCard
            className="p-0"
            contentClassName="space-y-0"
            description="Item-level outcomes for this job. Technical columns stay in the table while summary context remains above."
            title="Job items"
          >
            <ScrollArea className="max-h-[62vh]">
              <table className="w-full min-w-[1000px] text-sm">
                <thead className="sticky top-0 bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2">stable_key</th>
                    <th className="px-3 py-2">title</th>
                    <th className="px-3 py-2">doc_type</th>
                    <th className="px-3 py-2">status</th>
                    <th className="px-3 py-2">attempt</th>
                    <th className="px-3 py-2">document_id</th>
                    <th className="px-3 py-2">error</th>
                    <th className="px-3 py-2">updated_at</th>
                  </tr>
                </thead>
                <tbody>
                  {job.items.map((item) => (
                    <tr className="border-t align-top" key={item.id}>
                      <td className="px-3 py-2 text-xs">{item.stable_key}</td>
                      <td className="px-3 py-2">{item.title}</td>
                      <td className="px-3 py-2">{item.doc_type}</td>
                      <td className="px-3 py-2">
                        <PolicyStatusBadge status={item.status} />
                      </td>
                      <td className="px-3 py-2">{item.attempt}</td>
                      <td className="px-3 py-2 text-xs text-muted-foreground">{item.document_id ?? "-"}</td>
                      <td
                        className={`px-3 py-2 text-xs ${
                          item.error_message ? "text-destructive" : "text-muted-foreground"
                        }`}
                      >
                        {item.error_message ?? "-"}
                      </td>
                      <td className="px-3 py-2 text-xs text-muted-foreground">{formatPolicyDate(item.updated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollArea>
          </AppSectionCard>
        )}
      </div>

      <ConfirmDialog
        confirmLabel={retryMutation.isPending ? "Retrying..." : "Retry failed items"}
        description="This will create a new ingest job using the failed items from the current run."
        isBusy={retryMutation.isPending}
        onClose={() => setRetryDialogOpen(false)}
        onConfirm={() => {
          void handleRetry();
        }}
        open={retryDialogOpen}
        title="Retry failed items?"
      />
    </section>
  );
}
