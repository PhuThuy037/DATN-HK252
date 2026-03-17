import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { AuthUser } from "@/features/auth/types/authTypes";

type AuthState = {
  accessToken: string | null;
  refreshToken: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  hasHydrated: boolean;
  setAuth: (payload: {
    accessToken: string;
    refreshToken: string;
    user: AuthUser;
  }) => void;
  updateTokens: (payload: {
    accessToken: string;
    refreshToken: string;
  }) => void;
  setUser: (user: AuthUser | null) => void;
  clearAuth: () => void;
  setHasHydrated: (value: boolean) => void;
};

export const AUTH_STORAGE_KEY = "sentinel-auth-storage";

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
      hasHydrated: false,
      setAuth: ({ accessToken, refreshToken, user }) =>
        set({
          accessToken,
          refreshToken,
          user,
          isAuthenticated: true,
        }),
      updateTokens: ({ accessToken, refreshToken }) =>
        set((state) => ({
          accessToken,
          refreshToken,
          isAuthenticated: Boolean(state.user || accessToken),
        })),
      setUser: (user) => set({ user }),
      clearAuth: () =>
        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          isAuthenticated: false,
        }),
      setHasHydrated: (value) => set({ hasHydrated: value }),
    }),
    {
      name: AUTH_STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    }
  )
);
