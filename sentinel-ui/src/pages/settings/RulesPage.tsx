import { FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import { Textarea } from "@/shared/ui/textarea";
import { toast } from "@/shared/ui/use-toast";
import { RuleForm } from "@/features/rules/components/RuleForm";
import {
  useCreateRule,
  useDebugEvaluate,
  useDeleteRule,
  useEffectiveRules,
  useRuleChangeLogs,
  useRules,
  useToggleGlobalRule,
  useUpdateRule,
} from "@/features/rules/hooks";
import { useRuleSetStore } from "@/features/rules/store/ruleSetStore";
import type { CreateRuleRequest, Rule, UpdateRuleRequest } from "@/features/rules/types";

type RulesPageLocationState = {
  highlightRuleId?: string;
  openEditForRuleId?: string;
  source?: string;
};

function formatDateTime(value?: string) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function isGlobalRule(rule: Rule) {
  const origin = (rule.origin ?? "").toLowerCase();
  return origin.includes("global");
}

function RuleModal({
  title,
  open,
  onClose,
  children,
}: {
  title: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="max-h-[90vh] w-full max-w-2xl overflow-y-auto p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <Button onClick={onClose} size="sm" type="button" variant="outline">
            Close
          </Button>
        </div>
        {children}
      </Card>
    </div>
  );
}

export function RulesPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const locationState = (location.state as RulesPageLocationState | null) ?? null;
  const searchParams = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const editRuleIdFromQuery = searchParams.get("editRuleId")?.trim() ?? "";
  const [createOpen, setCreateOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<Rule | null>(null);
  const [debugContent, setDebugContent] = useState("");
  const [activeTab, setActiveTab] = useState("my-rules");

  const currentRuleSetId = useRuleSetStore((state) => state.currentRuleSetId);
  const currentRuleSet = useRuleSetStore((state) => state.currentRuleSet);
  const isRuleSetResolved = useRuleSetStore((state) => state.isRuleSetResolved);

  const rulesQuery = useRules(currentRuleSetId ?? undefined);
  const effectiveRulesQuery = useEffectiveRules();
  const changeLogsQuery = useRuleChangeLogs(currentRuleSetId ?? undefined, { limit: 50 });
  const createRuleMutation = useCreateRule(currentRuleSetId ?? undefined);
  const updateRuleMutation = useUpdateRule(currentRuleSetId ?? undefined);
  const deleteRuleMutation = useDeleteRule(currentRuleSetId ?? undefined);
  const toggleGlobalRuleMutation = useToggleGlobalRule(currentRuleSetId ?? undefined);
  const debugEvaluateMutation = useDebugEvaluate();

  const rules = useMemo(() => rulesQuery.data ?? [], [rulesQuery.data]);
  const myRules = useMemo(() => rules.filter((rule) => !isGlobalRule(rule)), [rules]);
  const globalRules = useMemo(() => rules.filter((rule) => isGlobalRule(rule)), [rules]);
  const changeLogs = useMemo(() => changeLogsQuery.data ?? [], [changeLogsQuery.data]);
  const effectiveRules = useMemo(
    () => effectiveRulesQuery.data ?? [],
    [effectiveRulesQuery.data]
  );

  useEffect(() => {
    const targetRuleId = editRuleIdFromQuery || locationState?.openEditForRuleId?.trim() || "";
    if (!targetRuleId || rules.length === 0) {
      return;
    }

    const targetRule = rules.find((rule) => rule.id === targetRuleId);
    if (targetRule) {
      setActiveTab(isGlobalRule(targetRule) ? "global-rules" : "my-rules");
      setEditingRule(targetRule);
    } else {
      toast({
        title: "Rule not found",
        description: "Unable to open the requested rule for editing.",
        variant: "destructive",
      });
    }

    navigate(location.pathname, { replace: true });
  }, [editRuleIdFromQuery, location.pathname, locationState?.openEditForRuleId, navigate, rules]);

  const handleCreateRule = async (payload: CreateRuleRequest | UpdateRuleRequest) => {
    try {
      await createRuleMutation.mutateAsync(payload as CreateRuleRequest);
      toast({
        title: "Rule created",
        description: "Rule has been created successfully.",
        variant: "success",
      });
      setCreateOpen(false);
    } catch (error) {
      toast({
        title: "Create failed",
        description: error instanceof Error ? error.message : "Failed to create rule.",
        variant: "destructive",
      });
    }
  };

  const handleUpdateRule = async (payload: CreateRuleRequest | UpdateRuleRequest) => {
    if (!editingRule) {
      return;
    }
    try {
      await updateRuleMutation.mutateAsync({
        ruleId: editingRule.id,
        payload: payload as UpdateRuleRequest,
      });
      toast({
        title: "Rule updated",
        description: "Rule has been updated successfully.",
        variant: "success",
      });
      setEditingRule(null);
    } catch (error) {
      toast({
        title: "Update failed",
        description: error instanceof Error ? error.message : "Failed to update rule.",
        variant: "destructive",
      });
    }
  };

  const handleDeleteRule = async (rule: Rule) => {
    const confirmed = window.confirm(`Delete rule "${rule.name}"?`);
    if (!confirmed) {
      return;
    }

    try {
      await deleteRuleMutation.mutateAsync(rule.id);
      toast({
        title: "Rule deleted",
        description: "Rule deleted successfully.",
        variant: "success",
      });
    } catch (error) {
      toast({
        title: "Delete failed",
        description: error instanceof Error ? error.message : "Failed to delete rule.",
        variant: "destructive",
      });
    }
  };

  const handleToggleEnabled = async (rule: Rule, enabled: boolean) => {
    try {
      if (isGlobalRule(rule)) {
        if (!rule.stable_key) {
          toast({
            title: "Global rule is read-only",
            description: "This global rule cannot be toggled because stable key is missing.",
            variant: "destructive",
          });
          return;
        }

        await toggleGlobalRuleMutation.mutateAsync({
          stableKey: rule.stable_key,
          payload: { enabled },
        });
      } else {
        await updateRuleMutation.mutateAsync({
          ruleId: rule.id,
          payload: { enabled },
        });
      }

      toast({
        title: "Rule updated",
        description: `Rule ${enabled ? "enabled" : "disabled"} successfully.`,
        variant: "success",
      });
    } catch (error) {
      toast({
        title: "Toggle failed",
        description: error instanceof Error ? error.message : "Failed to toggle rule.",
        variant: "destructive",
      });
    }
  };

  const handleEvaluate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const content = debugContent.trim();
    if (!content) {
      return;
    }

    try {
      await debugEvaluateMutation.mutateAsync({ content });
    } catch (error) {
      toast({
        title: "Evaluate failed",
        description: error instanceof Error ? error.message : "Failed to evaluate text.",
        variant: "destructive",
      });
    }
  };

  if (!isRuleSetResolved) {
    return <p className="p-6 text-sm text-muted-foreground">Resolving workspace...</p>;
  }

  if (!currentRuleSetId) {
    return <Navigate replace to="/onboarding/rule-set" />;
  }

  return (
    <section className="h-full overflow-auto p-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold">Rules Management</h1>
            <p className="text-sm text-muted-foreground">
              Rules below belong to your current workspace rule set.
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Workspace: {currentRuleSet?.name ?? "Current rule set"}
            </p>
          </div>

          {activeTab === "my-rules" && (
            <Button onClick={() => setCreateOpen(true)} type="button">
              New Rule
            </Button>
          )}
        </header>

        <Tabs onValueChange={setActiveTab} value={activeTab}>
          <TabsList className="flex flex-wrap">
            <TabsTrigger value="my-rules">My Rules</TabsTrigger>
            <TabsTrigger value="global-rules">Global Rules</TabsTrigger>
            <TabsTrigger value="effective-rules">Effective Rules</TabsTrigger>
            <TabsTrigger value="change-logs">Change Logs</TabsTrigger>
            <TabsTrigger value="debug">Debug Evaluate</TabsTrigger>
          </TabsList>

          <TabsContent value="my-rules">
            <Card className="p-4">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-base font-semibold">Custom rules in this rule set</h2>
                <Badge>{myRules.length} rules</Badge>
              </div>
              <RuleTable
                allowEdit
                allowDelete
                allowToggle
                emptyText="No custom rules yet. Create your first rule."
                isError={rulesQuery.isError}
                isLoading={rulesQuery.isLoading}
                onDeleteRule={handleDeleteRule}
                onEditRule={setEditingRule}
                onToggleEnabled={handleToggleEnabled}
                rules={myRules}
                showOrigin
              />
            </Card>
          </TabsContent>

          <TabsContent value="global-rules">
            <Card className="p-4">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-base font-semibold">Global rules (read-only)</h2>
                <Badge className="bg-muted text-muted-foreground">
                  {globalRules.length} rules
                </Badge>
              </div>
              <RuleTable
                allowDelete={false}
                allowEdit={false}
                allowToggle
                emptyText="No global rules available."
                isError={rulesQuery.isError}
                isLoading={rulesQuery.isLoading}
                onDeleteRule={handleDeleteRule}
                onEditRule={setEditingRule}
                onToggleEnabled={handleToggleEnabled}
                rules={globalRules}
                showOrigin
              />
            </Card>
          </TabsContent>

          <TabsContent value="effective-rules">
            <Card className="space-y-3 p-4">
              <h2 className="text-base font-semibold">Effective rules</h2>

              {effectiveRulesQuery.isLoading && (
                <p className="text-sm text-muted-foreground">Loading effective rules...</p>
              )}

              {effectiveRulesQuery.isError && (
                <p className="text-sm text-destructive">Failed to load effective rules.</p>
              )}

              {!effectiveRulesQuery.isLoading &&
                !effectiveRulesQuery.isError &&
                effectiveRules.length === 0 && (
                  <p className="text-sm text-muted-foreground">No effective rules found.</p>
                )}

              {effectiveRules.map((rule) => (
                <div className="rounded-md border p-3 text-sm" key={rule.id ?? rule.stable_key}>
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium">{rule.name}</p>
                    <Badge>{rule.action}</Badge>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
                    <span>Priority: {rule.priority ?? "-"}</span>
                    <span>Enabled: {rule.enabled ? "yes" : "no"}</span>
                    <span>Origin: {rule.origin ?? "-"}</span>
                  </div>
                </div>
              ))}
            </Card>
          </TabsContent>

          <TabsContent value="change-logs">
            <Card className="space-y-3 p-4">
              <h2 className="text-base font-semibold">Rule change logs</h2>

              {changeLogsQuery.isLoading && (
                <p className="text-sm text-muted-foreground">Loading change logs...</p>
              )}
              {changeLogsQuery.isError && (
                <p className="text-sm text-destructive">Failed to load change logs.</p>
              )}
              {!changeLogsQuery.isLoading &&
                !changeLogsQuery.isError &&
                changeLogs.length === 0 && (
                  <p className="text-sm text-muted-foreground">No change logs yet.</p>
                )}

              {changeLogs.map((log, index) => (
                <div className="rounded-lg border p-3 text-sm" key={log.id ?? `${index}-${log.created_at}`}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium">{log.action ?? "unknown_action"}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatDateTime(log.created_at)}
                    </p>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Reason: {log.reason ?? "-"}
                  </p>
                  <details className="mt-2 text-xs">
                    <summary className="cursor-pointer text-muted-foreground">
                      Raw JSON
                    </summary>
                    <pre className="mt-2 overflow-auto rounded bg-muted p-2">
                      {JSON.stringify(
                        {
                          changed_fields: log.changed_fields,
                          before_json: log.before_json,
                          after_json: log.after_json,
                        },
                        null,
                        2
                      )}
                    </pre>
                  </details>
                </div>
              ))}
            </Card>
          </TabsContent>

          <TabsContent value="debug">
            <Card className="space-y-4 p-4">
              <div>
                <h2 className="text-base font-semibold">Debug evaluate</h2>
                <p className="text-sm text-muted-foreground">
                  Quick test text against current rules.
                </p>
              </div>

              <form className="space-y-3" onSubmit={handleEvaluate}>
                <Textarea
                  className="min-h-[140px]"
                  onChange={(event) => setDebugContent(event.target.value)}
                  placeholder="Nhap noi dung can evaluate..."
                  value={debugContent}
                />
                <Button disabled={debugEvaluateMutation.isPending || !debugContent.trim()} type="submit">
                  {debugEvaluateMutation.isPending ? "Evaluating..." : "Evaluate"}
                </Button>
              </form>

              {debugEvaluateMutation.isError && (
                <p className="text-sm text-destructive">Failed to evaluate text.</p>
              )}

              {debugEvaluateMutation.data && (
                <div className="space-y-3 rounded-lg border p-3 text-sm">
                  <div>
                    <p className="text-xs text-muted-foreground">Final action</p>
                    <p className="font-medium">{debugEvaluateMutation.data.final_action ?? "-"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Matched rules</p>
                    <pre className="mt-1 overflow-auto rounded bg-muted p-2 text-xs">
                      {JSON.stringify(debugEvaluateMutation.data.matched_rules ?? [], null, 2)}
                    </pre>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Signals</p>
                    <pre className="mt-1 overflow-auto rounded bg-muted p-2 text-xs">
                      {JSON.stringify(debugEvaluateMutation.data.signals ?? {}, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      <RuleModal onClose={() => setCreateOpen(false)} open={createOpen} title="Create new rule">
        <RuleForm
          isSubmitting={createRuleMutation.isPending}
          mode="create"
          onCancel={() => setCreateOpen(false)}
          onSubmit={(payload) => void handleCreateRule(payload)}
        />
      </RuleModal>

      <RuleModal
        onClose={() => setEditingRule(null)}
        open={Boolean(editingRule)}
        title="Edit rule"
      >
        <RuleForm
          initialRule={editingRule}
          isSubmitting={updateRuleMutation.isPending}
          mode="edit"
          onCancel={() => setEditingRule(null)}
          onSubmit={(payload) => void handleUpdateRule(payload)}
        />
      </RuleModal>
    </section>
  );
}

function RuleTable({
  rules,
  isLoading,
  isError,
  emptyText,
  allowEdit,
  allowDelete,
  allowToggle,
  showOrigin,
  onEditRule,
  onDeleteRule,
  onToggleEnabled,
}: {
  rules: Rule[];
  isLoading: boolean;
  isError: boolean;
  emptyText: string;
  allowEdit: boolean;
  allowDelete: boolean;
  allowToggle: boolean;
  showOrigin?: boolean;
  onEditRule: (rule: Rule) => void;
  onDeleteRule: (rule: Rule) => void;
  onToggleEnabled: (rule: Rule, enabled: boolean) => void;
}) {
  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading rules...</p>;
  }

  if (isError) {
    return <p className="text-sm text-destructive">Failed to load rules.</p>;
  }

  if (rules.length === 0) {
    return <p className="text-sm text-muted-foreground">{emptyText}</p>;
  }

  return (
    <ScrollArea className="max-h-[520px]">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b text-left text-xs uppercase text-muted-foreground">
            <th className="px-2 py-2">Name</th>
            <th className="px-2 py-2">Action</th>
            <th className="px-2 py-2">Severity</th>
            <th className="px-2 py-2">Priority</th>
            <th className="px-2 py-2">Enabled</th>
            {showOrigin && <th className="px-2 py-2">Type</th>}
            <th className="px-2 py-2">Updated</th>
            <th className="px-2 py-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rules.map((rule) => {
            const global = isGlobalRule(rule);
            const canToggleGlobal = global && Boolean(rule.stable_key);
            return (
              <tr className="border-b align-top" key={rule.id}>
                <td className="px-2 py-2">
                  <p className="font-medium">{rule.name}</p>
                  <p className="text-xs text-muted-foreground">{rule.stable_key ?? "-"}</p>
                </td>
                <td className="px-2 py-2">
                  <Badge>{rule.action}</Badge>
                </td>
                <td className="px-2 py-2">{rule.severity ?? "-"}</td>
                <td className="px-2 py-2">{rule.priority ?? "-"}</td>
                <td className="px-2 py-2">
                  <label className="inline-flex items-center gap-2">
                    <input
                      checked={rule.enabled}
                      disabled={!allowToggle || (global && !canToggleGlobal)}
                      onChange={(event) => onToggleEnabled(rule, event.target.checked)}
                      type="checkbox"
                    />
                    <span className="text-xs">{rule.enabled ? "On" : "Off"}</span>
                  </label>
                </td>
                {showOrigin && (
                  <td className="px-2 py-2">
                    <Badge
                      className={
                        global
                          ? "bg-muted text-muted-foreground"
                          : "border-dashed text-muted-foreground"
                      }
                    >
                      {global ? "Global" : "Custom"}
                    </Badge>
                  </td>
                )}
                <td className="px-2 py-2 text-xs text-muted-foreground">
                  {formatDateTime(rule.updated_at)}
                </td>
                <td className="px-2 py-2">
                  <div className="flex min-w-[96px] flex-col gap-2">
                    {allowEdit ? (
                      <Button
                        className="h-8 justify-center whitespace-nowrap"
                        disabled={global}
                        onClick={() => onEditRule(rule)}
                        size="sm"
                        type="button"
                        variant="outline"
                      >
                        Edit
                      </Button>
                    ) : (
                      <Button
                        className="h-8 justify-center whitespace-nowrap"
                        disabled
                        size="sm"
                        type="button"
                        variant="outline"
                      >
                        View
                      </Button>
                    )}
                    {allowDelete ? (
                      <Button
                        className="h-8 justify-center whitespace-nowrap"
                        disabled={global || rule.can_soft_delete === false}
                        onClick={() => onDeleteRule(rule)}
                        size="sm"
                        type="button"
                        variant="outline"
                      >
                        Delete
                      </Button>
                    ) : (
                      <Button
                        className="h-8 justify-center whitespace-nowrap"
                        disabled
                        size="sm"
                        type="button"
                        variant="outline"
                      >
                        Read only
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </ScrollArea>
  );
}
