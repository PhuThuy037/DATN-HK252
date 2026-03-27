import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { extractAuthErrorMessage } from "@/features/auth/api/authApi";
import { useCreateRuleSet } from "@/features/rules/hooks/useCreateRuleSet";
import { useRuleSetStore } from "@/features/rules/store/ruleSetStore";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppButton } from "@/shared/ui/app-button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { FieldHelpText } from "@/shared/ui/field-help-text";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { toast } from "@/shared/ui/use-toast";

export function OnboardingRuleSetPage() {
  const navigate = useNavigate();
  const createRuleSetMutation = useCreateRuleSet();
  const setCurrentRuleSet = useRuleSetStore((state) => state.setCurrentRuleSet);
  const [name, setName] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage("");

    const trimmedName = name.trim();
    if (!trimmedName) {
      setErrorMessage("Rule set name is required.");
      return;
    }

    try {
      const createdRuleSet = await createRuleSetMutation.mutateAsync({
        name: trimmedName,
      });
      setCurrentRuleSet(createdRuleSet);
      toast({
        title: "Workspace ready",
        description: "Your rule set has been created.",
        variant: "success",
      });
      navigate("/app/chat", { replace: true });
    } catch (error) {
      const message = extractAuthErrorMessage(error);
      setErrorMessage(message);
      toast({
        title: "Create rule set failed",
        description: message,
        variant: "destructive",
      });
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,rgba(37,99,235,0.12),transparent_32%),linear-gradient(180deg,rgba(248,250,252,1),rgba(255,255,255,1))] px-6 py-12">
      <Card className="w-full max-w-lg rounded-[28px] border-border/80 bg-background/96 shadow-app-lg">
        <CardHeader>
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">Sentinel UI</p>
            <CardTitle className="text-title">Create your workspace</CardTitle>
            <p className="text-sm text-muted-foreground">
              Start by creating your first rule set. It will power new conversations across the app.
            </p>
          </div>
        </CardHeader>

        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <Label htmlFor="ruleSetName" required>
                Workspace name
              </Label>
              <Input
                id="ruleSetName"
                onChange={(event) => setName(event.target.value)}
                placeholder="My Compliance Workspace"
                value={name}
              />
              <FieldHelpText>Pick a clear name so teammates recognize this workspace later.</FieldHelpText>
            </div>

            {errorMessage ? (
              <AppAlert description={errorMessage} title="Workspace setup failed" variant="error" />
            ) : null}

            <AppButton
              className="w-full"
              disabled={createRuleSetMutation.isPending}
              type="submit"
            >
              {createRuleSetMutation.isPending ? "Creating workspace..." : "Create workspace"}
            </AppButton>

            <p className="text-sm text-muted-foreground">
              You can rename the workspace and fine-tune its rules after setup.
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
