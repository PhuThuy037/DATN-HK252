import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "react-router-dom";
import { extractAuthErrorMessage, register } from "@/features/auth/api/authApi";
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

const registerSchema = z
  .object({
    name: z.string().min(1, "Name is required"),
    email: z
      .string()
      .min(1, "Email is required")
      .email("Please enter a valid email address"),
    password: z
      .string()
      .min(1, "Password is required")
      .min(6, "Password must be at least 6 characters"),
    confirmPassword: z.string().min(1, "Please confirm your password"),
  })
  .refine((values) => values.password === values.confirmPassword, {
    path: ["confirmPassword"],
    message: "Passwords do not match",
  });

type RegisterFormValues = z.infer<typeof registerSchema>;

export function RegisterPage() {
  const navigate = useNavigate();
  const [serverError, setServerError] = useState("");

  const registerMutation = useMutation({
    mutationFn: register,
  });

  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      name: "",
      email: "",
      password: "",
      confirmPassword: "",
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    setServerError("");

    try {
      await registerMutation.mutateAsync({
        name: values.name.trim(),
        email: values.email.trim(),
        password: values.password,
      });

      toast({
        title: "Register successful",
        description: "Your account has been created. Please login.",
        variant: "success",
      });

      navigate("/login");
    } catch (error) {
      const message = extractAuthErrorMessage(error);
      setServerError(message);
      toast({
        title: "Register failed",
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
            <CardTitle className="text-title">Create account</CardTitle>
            <CardDescription>Register to access your compliance workspace.</CardDescription>
          </div>
        </CardHeader>

        <CardContent>
          <form className="space-y-4" onSubmit={onSubmit}>
            <div className="space-y-2">
              <Label htmlFor="name" required>Name</Label>
              <Input
                className={form.formState.errors.name ? "border-destructive focus-visible:ring-destructive" : undefined}
                id="name"
                placeholder="Your name"
                type="text"
                {...form.register("name")}
              />
              <FieldHelpText>This name helps teammates identify your account.</FieldHelpText>
              {form.formState.errors.name ? <InlineErrorText>{form.formState.errors.name.message}</InlineErrorText> : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor="email" required>Email</Label>
              <Input
                className={form.formState.errors.email ? "border-destructive focus-visible:ring-destructive" : undefined}
                id="email"
                placeholder="you@example.com"
                type="email"
                {...form.register("email")}
              />
              <FieldHelpText>Use a work email you can access for future sign-in.</FieldHelpText>
              {form.formState.errors.email ? <InlineErrorText>{form.formState.errors.email.message}</InlineErrorText> : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" required>Password</Label>
              <Input
                className={form.formState.errors.password ? "border-destructive focus-visible:ring-destructive" : undefined}
                id="password"
                placeholder="At least 6 characters"
                type="password"
                {...form.register("password")}
              />
              <FieldHelpText>Choose a password with at least 6 characters.</FieldHelpText>
              {form.formState.errors.password ? <InlineErrorText>{form.formState.errors.password.message}</InlineErrorText> : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirmPassword" required>Confirm password</Label>
              <Input
                className={form.formState.errors.confirmPassword ? "border-destructive focus-visible:ring-destructive" : undefined}
                id="confirmPassword"
                placeholder="Re-enter password"
                type="password"
                {...form.register("confirmPassword")}
              />
              <FieldHelpText>Re-enter the same password to confirm.</FieldHelpText>
              {form.formState.errors.confirmPassword ? <InlineErrorText>{form.formState.errors.confirmPassword.message}</InlineErrorText> : null}
            </div>

            {serverError ? <AppAlert description={serverError} title="Registration failed" variant="error" /> : null}

            <AppButton className="w-full" disabled={registerMutation.isPending} type="submit">
              {registerMutation.isPending ? "Creating account..." : "Create account"}
            </AppButton>

            <p className="text-sm text-muted-foreground">
              Already have an account?{" "}
              <Link className="font-medium text-primary underline-offset-4 hover:underline" to="/login">
                Login
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
