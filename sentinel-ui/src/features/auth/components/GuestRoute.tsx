import { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuthStore } from "@/features/auth/store/authStore";

type GuestRouteProps = {
  children: ReactNode;
};

export function GuestRoute({ children }: GuestRouteProps) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const hasHydrated = useAuthStore((state) => state.hasHydrated);

  if (!hasHydrated) {
    return null;
  }

  if (isAuthenticated) {
    return <Navigate replace to="/app/chat" />;
  }

  return <>{children}</>;
}
