import { ArrowLeft, RotateCcw } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { getPolicyErrorMessage } from "@/features/policies/api/policiesApi";
import { PolicyStatusBadge, formatPolicyDate, shortPolicyId } from "@/features/policies/components";
import { usePolicyIngestJobDetail, useRetryPolicyIngestJob } from "@/features/policies/hooks";
import { useMyRuleSets } from "@/features/rules/hooks";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { toast } from "@/shared/ui/use-toast";

export function PolicyJobDetailPage() {
  const navigate = useNavigate();
  const { jobId } = useParams();

  const myRuleSetsQuery = useMyRuleSets();
  const ruleSetId = myRuleSetsQuery.data?.[0]?.id;

  const detailQuery = usePolicyIngestJobDetail(ruleSetId, jobId);
  const retryMutation = useRetryPolicyIngestJob(ruleSetId, jobId);

  const handleRetry = async () => {
    if (!jobId) {
      return;
    }
    const confirmed = window.confirm("Retry failed items from this job?");
    if (!confirmed) {
      return;
    }

    try {
      const retried = await retryMutation.mutateAsync();
      toast({
        title: "Retry job created",
        description: `New job ${shortPolicyId(retried.id)} has been queued.`,
        variant: "success",
      });
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
    return <section className="p-6 text-sm text-muted-foreground">Loading job detail...</section>;
  }

  if (myRuleSetsQuery.isError || !ruleSetId) {
    return (
      <section className="p-6">
        <Card className="p-4 text-sm text-destructive">Unable to resolve current rule set.</Card>
      </section>
    );
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <section className="p-6">
        <Card className="p-4 text-sm text-destructive">
          {getPolicyErrorMessage(detailQuery.error, "Unable to load ingest job detail")}
        </Card>
      </section>
    );
  }

  const job = detailQuery.data;
  const canRetry = job.failed_items > 0;

  return (
    <section className="h-full overflow-auto p-6">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4">
        <div className="flex items-center justify-between">
          <Button onClick={() => navigate("/app/policies/jobs")} size="sm" type="button" variant="outline">
            <ArrowLeft className="mr-1 h-4 w-4" />
            Back to jobs
          </Button>

          {canRetry && (
            <Button
              disabled={retryMutation.isPending}
              onClick={() => {
                void handleRetry();
              }}
              size="sm"
              type="button"
            >
              <RotateCcw className="mr-1 h-4 w-4" />
              {retryMutation.isPending ? "Retrying..." : "Retry failed items"}
            </Button>
          )}
        </div>

        <Card className="space-y-3 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold">Job {shortPolicyId(job.id)}</p>
            <PolicyStatusBadge status={job.status} />
          </div>

          <div className="grid gap-2 text-sm md:grid-cols-4">
            <p>Total: {job.total_items}</p>
            <p>Success: {job.success_items}</p>
            <p>Failed: {job.failed_items}</p>
            <p>Skipped: {job.skipped_items}</p>
          </div>

          <div className="grid gap-1 text-xs text-muted-foreground md:grid-cols-2">
            <p>created_at: {formatPolicyDate(job.created_at)}</p>
            <p>started_at: {formatPolicyDate(job.started_at)}</p>
            <p>finished_at: {formatPolicyDate(job.finished_at)}</p>
            <p>retry_of_job_id: {job.retry_of_job_id ?? "-"}</p>
          </div>

          <details className="rounded-md border p-2 text-xs">
            <summary className="cursor-pointer font-medium text-muted-foreground">error_json</summary>
            <pre className="mt-2 overflow-auto rounded bg-muted p-2 text-[11px]">
              {JSON.stringify(job.error_json ?? null, null, 2)}
            </pre>
          </details>
        </Card>

        <Card className="p-0">
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
                {job.items.length === 0 && (
                  <tr>
                    <td className="px-3 py-6 text-center text-sm text-muted-foreground" colSpan={8}>
                      No job items.
                    </td>
                  </tr>
                )}

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
                    <td className="px-3 py-2 text-xs text-destructive">{item.error_message ?? "-"}</td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">{formatPolicyDate(item.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollArea>
        </Card>
      </div>
    </section>
  );
}
