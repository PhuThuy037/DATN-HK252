import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { PolicyDocumentsTab, PolicyJobsTab } from "@/features/policies/components";
import { useMyRuleSets } from "@/features/rules/hooks";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppLoadingState } from "@/shared/ui/app-loading-state";
import { AppPageHeader } from "@/shared/ui/app-page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs";

type PoliciesTab = "documents" | "jobs";

function inferTabFromPath(pathname: string): PoliciesTab {
  if (pathname.startsWith("/app/policies/jobs")) {
    return "jobs";
  }
  return "documents";
}

export function PoliciesPage() {
  const location = useLocation();
  const navigate = useNavigate();

  const myRuleSetsQuery = useMyRuleSets();
  const ruleSetId = myRuleSetsQuery.data?.[0]?.id;

  const defaultTab = useMemo(() => inferTabFromPath(location.pathname), [location.pathname]);
  const [activeTab, setActiveTab] = useState<PoliciesTab>(defaultTab);

  useEffect(() => {
    setActiveTab(inferTabFromPath(location.pathname));
  }, [location.pathname]);

  if (myRuleSetsQuery.isLoading) {
    return (
      <section className="p-6">
        <AppLoadingState
          className="mx-auto max-w-3xl"
          description="Loading the current rule set before showing policy documents and ingest jobs."
          title="Loading policies"
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

  return (
    <section className="h-full overflow-auto p-6">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4">
        <AppPageHeader
          meta={`Rule set ID: ${ruleSetId}`}
          subtitle="Manage policy documents and ingest jobs for the current rule set."
          title="Policy Documents & Ingest"
        />

        <Tabs
          onValueChange={(value) => {
            const tab = value as PoliciesTab;
            setActiveTab(tab);
            navigate(tab === "documents" ? "/app/policies" : "/app/policies/jobs");
          }}
          value={activeTab}
        >
          <TabsList>
            <TabsTrigger value="documents">Documents</TabsTrigger>
            <TabsTrigger value="jobs">Ingest Jobs</TabsTrigger>
          </TabsList>

          <TabsContent value="documents">
            <PolicyDocumentsTab ruleSetId={ruleSetId} />
          </TabsContent>

          <TabsContent value="jobs">
            <PolicyJobsTab ruleSetId={ruleSetId} />
          </TabsContent>
        </Tabs>
      </div>
    </section>
  );
}
