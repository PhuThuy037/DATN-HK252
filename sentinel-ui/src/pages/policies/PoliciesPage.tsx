import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { PolicyDocumentsTab, PolicyJobsTab } from "@/features/policies/components";
import { useMyRuleSets } from "@/features/rules/hooks";
import { Card } from "@/shared/ui/card";
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
    return <section className="p-6 text-sm text-muted-foreground">Loading rule set...</section>;
  }

  if (myRuleSetsQuery.isError || !ruleSetId) {
    return (
      <section className="p-6">
        <Card className="p-4 text-sm text-destructive">Unable to resolve current rule set.</Card>
      </section>
    );
  }

  return (
    <section className="h-full overflow-auto p-6">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4">
        <header>
          <h1 className="text-xl font-semibold">Policy Documents & Ingest</h1>
          <p className="text-sm text-muted-foreground">
            Manage policy documents and ingest jobs for current rule set.
          </p>
          <p className="text-xs text-muted-foreground">Rule set ID: {ruleSetId}</p>
        </header>

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
