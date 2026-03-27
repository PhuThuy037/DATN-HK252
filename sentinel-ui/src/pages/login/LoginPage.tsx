import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "react-router-dom";
import { extractAuthErrorMessage } from "@/features/auth/api/authApi";
import { useLogin } from "@/features/auth/hooks/useLogin";
import { AppAlert } from "@/shared/ui/app-alert";
import { AppButton } from "@/shared/ui/app-button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/ui/card";
import { FieldHelpText } from "@/shared/ui/field-help-text";
import { Input } from "@/shared/ui/input";
import { InlineErrorText } from "@/shared/ui/inline-error-text";
import { Label } from "@/shared/ui/label";
import { toast } from "@/shared/ui/use-toast";

const loginSchema = z.object({
  email: z
    .string()
    .min(1, "Email is required")
    .email("Please enter a valid email address"),
  password: z
    .string()
    .min(1, "Password is required")
    .min(6, "Password must be at least 6 characters"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export function LoginPage() {
  const navigate = useNavigate();
  const [serverError, setServerError] = useState("");
  const loginMutation = useLogin();

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    setServerError("");

    try {
      await loginMutation.mutateAsync(values);

      toast({
        title: "Login successful",
        description: "Welcome back to Sentinel UI.",
        variant: "success",
      });

      navigate("/app/chat");
    } catch (error) {
      const message = extractAuthErrorMessage(error);
      setServerError(message);
      toast({
        title: "Login failed",
        description: message,
        variant: "destructive",
      });
    }
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,rgba(37,99,235,0.12),transparent_32%),linear-gradient(180deg,rgba(248,250,252,1),rgba(255,255,255,1))] px-6 py-12">
      <Card className="w-full max-w-md rounded-[28px] border-border/80 bg-background/96 shadow-app-lg">
        <CardHeader>
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">Sentinel UI</p>
            <CardTitle className="text-title">Login</CardTitle>
            <CardDescription>Sign in to continue to your chat workspace.</CardDescription>
          </div>
        </CardHeader>

        <CardContent>
          <form className="space-y-4" onSubmit={onSubmit}>
            <div className="space-y-2">
              <Label htmlFor="email" required>Email</Label>
              <Input
                autoComplete="email"
                className={form.formState.errors.email ? "border-destructive focus-visible:ring-destructive" : undefined}
                id="email"
                placeholder="you@example.com"
                type="email"
                {...form.register("email")}
              />
              <FieldHelpText>Use the email tied to your Sentinel workspace.</FieldHelpText>
              {form.formState.errors.email ? <InlineErrorText>{form.formState.errors.email.message}</InlineErrorText> : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" required>Password</Label>
              <Input
                autoComplete="current-password"
                className={form.formState.errors.password ? "border-destructive focus-visible:ring-destructive" : undefined}
                id="password"
                placeholder="Enter your password"
                type="password"
                {...form.register("password")}
              />
              <FieldHelpText>Passwords must be at least 6 characters.</FieldHelpText>
              {form.formState.errors.password ? <InlineErrorText>{form.formState.errors.password.message}</InlineErrorText> : null}
            </div>

            {serverError ? <AppAlert description={serverError} title="Login failed" variant="error" /> : null}

            <AppButton className="w-full" disabled={loginMutation.isPending} type="submit">
              {loginMutation.isPending ? "Signing in..." : "Sign in"}
            </AppButton>

            <p className="text-sm text-muted-foreground">
              No account?{" "}
              <Link className="font-medium text-primary underline-offset-4 hover:underline" to="/register">
                Register
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
