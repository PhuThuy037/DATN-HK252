import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "react-router-dom";
import { extractAuthErrorMessage, register } from "@/features/auth/api/authApi";
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
    <div className="flex min-h-screen items-center justify-center px-6 py-12">
      <Card className="w-full max-w-md shadow-sm">
        <CardHeader>
          <CardTitle>Create account</CardTitle>
          <CardDescription>Register to access your compliance workspace.</CardDescription>
        </CardHeader>

        <CardContent>
          <form className="space-y-4" onSubmit={onSubmit}>
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" placeholder="Your name" type="text" {...form.register("name")} />
              {form.formState.errors.name && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.name.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
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
                id="password"
                placeholder="At least 6 characters"
                type="password"
                {...form.register("password")}
              />
              {form.formState.errors.password && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.password.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm password</Label>
              <Input
                id="confirmPassword"
                placeholder="Re-enter password"
                type="password"
                {...form.register("confirmPassword")}
              />
              {form.formState.errors.confirmPassword && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.confirmPassword.message}
                </p>
              )}
            </div>

            {serverError && <p className="text-sm text-destructive">{serverError}</p>}

            <Button className="w-full" disabled={registerMutation.isPending} type="submit">
              {registerMutation.isPending ? "Creating account..." : "Create account"}
            </Button>

            <p className="text-sm text-muted-foreground">
              Already have an account?{" "}
              <Link className="underline" to="/login">
                Login
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
