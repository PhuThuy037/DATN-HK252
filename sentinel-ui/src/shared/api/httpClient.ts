import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import { env } from "@/shared/config/env";
import { AUTH_STORAGE_KEY, useAuthStore } from "@/features/auth/store/authStore";
import type {
  ApiEnvelope,
  RefreshTokenResponseData,
} from "@/features/auth/types/authTypes";

type RetryableRequest = InternalAxiosRequestConfig & { _retry?: boolean };

type PersistedAuthSnapshot = {
  state?: {
    accessToken?: string | null;
    refreshToken?: string | null;
  };
};

type PendingRequest = {
  resolve: (accessToken: string) => void;
  reject: (error: unknown) => void;
};

let isRefreshing = false;
let pendingRequests: PendingRequest[] = [];

function readPersistedTokens() {
  if (typeof window === "undefined") {
    return {
      accessToken: null,
      refreshToken: null,
    };
  }

  try {
    const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) {
      return {
        accessToken: null,
        refreshToken: null,
      };
    }

    const parsed = JSON.parse(raw) as PersistedAuthSnapshot;
    return {
      accessToken: parsed?.state?.accessToken ?? null,
      refreshToken: parsed?.state?.refreshToken ?? null,
    };
  } catch {
    return {
      accessToken: null,
      refreshToken: null,
    };
  }
}

function processPendingRequests(error: unknown, accessToken: string | null) {
  pendingRequests.forEach((request) => {
    if (error || !accessToken) {
      request.reject(error);
      return;
    }
    request.resolve(accessToken);
  });

  pendingRequests = [];
}

function redirectToLogin() {
  if (typeof window === "undefined") {
    return;
  }

  if (!window.location.pathname.startsWith("/login")) {
    window.location.assign("/login");
  }
}

const httpClient = axios.create({
  baseURL: env.apiBaseUrl,
  headers: {
    "Content-Type": "application/json",
  },
});

httpClient.interceptors.request.use((config) => {
  const persisted = readPersistedTokens();
  const token = useAuthStore.getState().accessToken ?? persisted.accessToken;

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

httpClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetryableRequest | undefined;
    const status = error.response?.status;
    const requestUrl = originalRequest?.url ?? "";

    if (!originalRequest || status !== 401) {
      return Promise.reject(error);
    }

    if (
      requestUrl.includes("/v1/auth/login") ||
      requestUrl.includes("/v1/auth/register") ||
      requestUrl.includes("/v1/auth/refresh")
    ) {
      return Promise.reject(error);
    }

    if (originalRequest._retry) {
      return Promise.reject(error);
    }

    const persisted = readPersistedTokens();
    const currentRefreshToken =
      useAuthStore.getState().refreshToken ?? persisted.refreshToken;

    if (!currentRefreshToken) {
      useAuthStore.getState().clearAuth();
      redirectToLogin();
      return Promise.reject(error);
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        pendingRequests.push({
          resolve: (newAccessToken) => {
            if (!originalRequest.headers) {
              originalRequest.headers = {};
            }
            originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
            resolve(httpClient(originalRequest));
          },
          reject: (queueError) => reject(queueError),
        });
      });
    }

    originalRequest._retry = true;
    isRefreshing = true;

    try {
      const refreshResponse = await axios.post<ApiEnvelope<RefreshTokenResponseData>>(
        `${env.apiBaseUrl}/v1/auth/refresh`,
        {
          refresh_token: currentRefreshToken,
        },
        {
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      const envelope = refreshResponse.data;
      if (!envelope.ok || !envelope.data) {
        throw new Error(envelope.error?.message ?? "Refresh token failed");
      }

      const nextAccessToken = envelope.data.access_token;
      const nextRefreshToken = envelope.data.refresh_token;

      useAuthStore.getState().updateTokens({
        accessToken: nextAccessToken,
        refreshToken: nextRefreshToken,
      });

      processPendingRequests(null, nextAccessToken);

      if (!originalRequest.headers) {
        originalRequest.headers = {};
      }
      originalRequest.headers.Authorization = `Bearer ${nextAccessToken}`;

      return httpClient(originalRequest);
    } catch (refreshError) {
      processPendingRequests(refreshError, null);
      useAuthStore.getState().clearAuth();
      redirectToLogin();
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  }
);

export { httpClient };
