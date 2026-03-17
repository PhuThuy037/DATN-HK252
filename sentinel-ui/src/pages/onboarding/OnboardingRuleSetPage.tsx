import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { extractAuthErrorMessage } from "@/features/auth/api/authApi";
import { useCreateRuleSet } from "@/features/rules/hooks/useCreateRuleSet";
import { useRuleSetStore } from "@/features/rules/store/ruleSetStore";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
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
    <div className="flex min-h-screen items-center justify-center px-6 py-12">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle>Create your workspace</CardTitle>
          <p className="text-sm text-muted-foreground">
            Start by creating your first rule set. This will be used for all new
            conversations.
          </p>
        </CardHeader>

        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <Label htmlFor="ruleSetName">Rule set name</Label>
              <Input
                id="ruleSetName"
                onChange={(event) => setName(event.target.value)}
                placeholder="My Compliance Workspace"
                value={name}
              />
            </div>

            {errorMessage && <p className="text-sm text-destructive">{errorMessage}</p>}

            <Button
              className="w-full"
              disabled={createRuleSetMutation.isPending}
              type="submit"
            >
              {createRuleSetMutation.isPending ? "Creating..." : "Create workspace"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
