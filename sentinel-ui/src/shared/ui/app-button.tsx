import type { ReactNode } from "react";
import { Button, type ButtonProps } from "@/shared/ui/button";

type AppButtonProps = Omit<ButtonProps, "variant"> & {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  leadingIcon?: ReactNode;
  trailingIcon?: ReactNode;
};

export function AppButton({
  variant = "primary",
  leadingIcon,
  trailingIcon,
  children,
  ...props
}: AppButtonProps) {
  const mappedVariant =
    variant === "danger"
      ? "destructive"
      : variant === "secondary"
        ? "secondary"
        : variant === "ghost"
          ? "ghost"
          : "default";

  return (
    <Button variant={mappedVariant} {...props}>
      {leadingIcon}
      {children}
      {trailingIcon}
    </Button>
  );
}
