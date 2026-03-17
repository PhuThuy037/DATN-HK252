import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { AxiosError } from "axios";
import { getMe } from "@/features/auth/api/authApi";
import type { ApiEnvelope } from "@/features/auth/types/authTypes";
import { useAuthStore } from "@/features/auth/store/authStore";

type UseMeOptions = {
  enabled?: boolean;
};

export function useMe(options?: UseMeOptions) {
  const clearAuth = useAuthStore((state) => state.clearAuth);
  const setUser = useAuthStore((state) => state.setUser);

  const query = useQuery({
    queryKey: ["auth", "me"],
    queryFn: getMe,
    enabled: options?.enabled ?? true,
    retry: false,
    staleTime: 60 * 1000,
  });

  useEffect(() => {
    if (query.data) {
      setUser(query.data);
    }
  }, [query.data, setUser]);

  useEffect(() => {
    if (!query.error) {
      return;
    }

    const axiosError = query.error as AxiosError<ApiEnvelope<null>> | undefined;
    if (axiosError?.response?.status === 401) {
      clearAuth();
    }
  }, [clearAuth, query.error]);

  return query;
}
