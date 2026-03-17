import { useMutation } from "@tanstack/react-query";
import { login } from "@/features/auth/api/authApi";
import { useAuthStore } from "@/features/auth/store/authStore";
import type { LoginRequest } from "@/features/auth/types/authTypes";

export function useLogin() {
  const setAuth = useAuthStore((state) => state.setAuth);

  return useMutation({
    mutationFn: (payload: LoginRequest) => login(payload),
    onSuccess: (data) => {
      setAuth({
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        user: data.user,
      });
    },
  });
}
