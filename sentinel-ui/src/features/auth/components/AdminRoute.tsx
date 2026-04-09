import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuthStore } from "@/features/auth/store/authStore";

type AdminRouteProps = {
  children: ReactNode;
};

export function AdminRoute({ children }: AdminRouteProps) {
  const user = useAuthStore((state) => state.user);

  if (user?.role !== "admin") {
    return <Navigate replace to="/app/chat" />;
  }

  return <>{children}</>;
}
