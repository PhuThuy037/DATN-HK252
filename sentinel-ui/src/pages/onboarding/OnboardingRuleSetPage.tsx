import { Link } from "react-router-dom";

export function OnboardingRuleSetPage() {
  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center px-6">
      <h1 className="text-2xl font-semibold">Rule Set Onboarding</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Create your first rule set to start chat workspace.
      </p>

      <div className="mt-6 rounded-md border border-dashed p-4 text-sm text-muted-foreground">
        Rule set creation form placeholder.
      </div>

      <div className="mt-6">
        <Link className="underline" to="/app/chat">
          Continue to workspace
        </Link>
      </div>
    </div>
  );
}
