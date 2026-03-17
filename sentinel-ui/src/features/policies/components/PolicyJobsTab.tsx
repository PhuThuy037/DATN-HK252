import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { getPolicyErrorMessage } from "@/features/policies/api/policiesApi";
import { PolicyStatusBadge, formatPolicyDate, shortPolicyId } from "@/features/policies/components/PolicyStatusBadge";
import { useCreatePolicyIngestJob, usePolicyIngestJobs } from "@/features/policies/hooks";
import type { PolicyIngestItemInput } from "@/features/policies/types";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { Textarea } from "@/shared/ui/textarea";
import { toast } from "@/shared/ui/use-toast";

const createItemsSchema = z.array(
  z.object({
    stable_key: z.string().trim().min(1).max(200),
    title: z.string().trim().min(1).max(300),
    content: z.string().trim().min(1),
    doc_type: z.string().trim().min(1).max(100).optional(),
    enabled: z.boolean().optional(),
  })
).min(1).max(200);

const defaultItemsJson = JSON.stringify(
  [
    {
      stable_key: "hr.privacy.policy.v1",
      title: "HR Privacy Policy",
      content: "Personal data must not be shared outside approved channels.",
      doc_type: "policy",
      enabled: true,
    },
  ],
  null,
  2
);

type PolicyJobsTabProps = {
  ruleSetId: string;
};

export function PolicyJobsTab({ ruleSetId }: PolicyJobsTabProps) {
  const navigate = useNavigate();

  const [itemsJson, setItemsJson] = useState(defaultItemsJson);
  const [validationError, setValidationError] = useState<string | null>(null);

  const jobsQuery = usePolicyIngestJobs(ruleSetId, 50);
  const createMutation = useCreatePolicyIngestJob(ruleSetId);

  const sortedJobs = useMemo(() => {
    const jobs = jobsQuery.data ?? [];
    return [...jobs].sort((a, b) => {
      const aTime = new Date(a.created_at).getTime();
      const bTime = new Date(b.created_at).getTime();
      return bTime - aTime;
    });
  }, [jobsQuery.data]);

  const handleCreateJob = async () => {
    setValidationError(null);

    let parsed: unknown;
    try {
      parsed = JSON.parse(itemsJson);
    } catch {
      setValidationError("Items JSON is invalid.");
      return;
    }

    const validated = createItemsSchema.safeParse(parsed);
    if (!validated.success) {
      setValidationError(validated.error.issues[0]?.message ?? "Invalid items payload");
      return;
    }

    try {
      const created = await createMutation.mutateAsync({
        items: validated.data as PolicyIngestItemInput[],
      });
      toast({
        title: "Ingest job created",
        description: `Job ${shortPolicyId(created.id)} is queued.`,
        variant: "success",
      });
      navigate(`/app/policies/jobs/${created.id}`);
    } catch (error) {
      toast({
        title: "Create job failed",
        description: getPolicyErrorMessage(error, "Unable to create ingest job"),
        variant: "destructive",
      });
    }
  };

  return (
    <div className="space-y-4">
      <Card className="space-y-3 p-4">
        <div>
          <p className="text-sm font-semibold">Create ingest job</p>
          <p className="text-xs text-muted-foreground">
            Input items JSON array. Each item needs stable_key, title, content.
          </p>
        </div>

        <Textarea
          className="min-h-[180px] font-mono text-xs"
          onChange={(event) => setItemsJson(event.target.value)}
          value={itemsJson}
        />

        {validationError && <p className="text-xs text-destructive">{validationError}</p>}

        <div className="flex justify-end">
          <Button
            disabled={createMutation.isPending}
            onClick={() => {
              void handleCreateJob();
            }}
            type="button"
          >
            {createMutation.isPending ? "Creating..." : "Create ingest job"}
          </Button>
        </div>
      </Card>

      {jobsQuery.isLoading && (
        <Card className="p-4 text-sm text-muted-foreground">Loading ingest jobs...</Card>
      )}

      {jobsQuery.isError && (
        <Card className="p-4 text-sm text-destructive">
          {getPolicyErrorMessage(jobsQuery.error, "Failed to load ingest jobs")}
        </Card>
      )}

      {!jobsQuery.isLoading && !jobsQuery.isError && sortedJobs.length === 0 && (
        <Card className="p-6 text-center">
          <p className="text-sm font-medium">No ingest jobs</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Create your first ingest job to add policy documents.
          </p>
        </Card>
      )}

      {sortedJobs.length > 0 && (
        <Card className="p-0">
          <ScrollArea className="max-h-[60vh]">
            <table className="w-full min-w-[980px] text-sm">
              <thead className="sticky top-0 bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">ID</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Total</th>
                  <th className="px-3 py-2">Success</th>
                  <th className="px-3 py-2">Failed</th>
                  <th className="px-3 py-2">Skipped</th>
                  <th className="px-3 py-2">Created</th>
                  <th className="px-3 py-2">Started</th>
                  <th className="px-3 py-2">Finished</th>
                </tr>
              </thead>
              <tbody>
                {sortedJobs.map((job) => (
                  <tr
                    className="cursor-pointer border-t hover:bg-muted/30"
                    key={job.id}
                    onClick={() => navigate(`/app/policies/jobs/${job.id}`)}
                  >
                    <td className="px-3 py-2 font-medium">{shortPolicyId(job.id)}</td>
                    <td className="px-3 py-2">
                      <PolicyStatusBadge status={job.status} />
                    </td>
                    <td className="px-3 py-2">{job.total_items}</td>
                    <td className="px-3 py-2">{job.success_items}</td>
                    <td className="px-3 py-2">{job.failed_items}</td>
                    <td className="px-3 py-2">{job.skipped_items}</td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">{formatPolicyDate(job.created_at)}</td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">{formatPolicyDate(job.started_at)}</td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">{formatPolicyDate(job.finished_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollArea>
        </Card>
      )}
    </div>
  );
}
