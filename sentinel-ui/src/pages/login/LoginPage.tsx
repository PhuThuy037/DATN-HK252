import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "react-router-dom";
import { extractAuthErrorMessage } from "@/features/auth/api/authApi";
import { useLogin } from "@/features/auth/hooks/useLogin";
import { Button } from "@/shared/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
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
      const response = await loginMutation.mutateAsync(values);
      // Temporary success handling for this step.
      // eslint-disable-next-line no-console
      console.log("Login success:", response);

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
    <div className="flex min-h-screen items-center justify-center px-6 py-12">
      <Card className="w-full max-w-md shadow-sm">
        <CardHeader>
          <CardTitle>Login</CardTitle>
          <CardDescription>Sign in to continue to your chat workspace.</CardDescription>
        </CardHeader>

        <CardContent>
          <form className="space-y-4" onSubmit={onSubmit}>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                autoComplete="email"
                id="email"
                placeholder="you@example.com"
                type="email"
                {...form.register("email")}
              />
              {form.formState.errors.email && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.email.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                autoComplete="current-password"
                id="password"
                placeholder="Enter your password"
                type="password"
                {...form.register("password")}
              />
              {form.formState.errors.password && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.password.message}
                </p>
              )}
            </div>

            {serverError && <p className="text-sm text-destructive">{serverError}</p>}

            <Button className="w-full" disabled={loginMutation.isPending} type="submit">
              {loginMutation.isPending ? "Signing in..." : "Sign in"}
            </Button>

            <p className="text-sm text-muted-foreground">
              No account?{" "}
              <Link className="underline" to="/register">
                Register
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
