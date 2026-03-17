import { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuthStore } from "@/features/auth/store/authStore";
import { useMe } from "@/features/auth/hooks/useMe";

type ProtectedRouteProps = {
  children: ReactNode;
};

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const hasHydrated = useAuthStore((state) => state.hasHydrated);
  const accessToken = useAuthStore((state) => state.accessToken);

  const meQuery = useMe({
    enabled: hasHydrated && isAuthenticated && Boolean(accessToken),
  });

  if (!hasHydrated) {
    return null;
  }

  if (!isAuthenticated || !accessToken) {
    return <Navigate replace to="/login" />;
  }

  if (meQuery.isLoading) {
    return null;
  }

  if (meQuery.isError) {
    return <Navigate replace to="/login" />;
  }

  return <>{children}</>;
}
