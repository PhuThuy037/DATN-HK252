import { AxiosError } from "axios";
import { httpClient } from "@/shared/api/httpClient";
import { env } from "@/shared/config/env";
import axios from "axios";
import type {
  AuthUser,
  ApiEnvelope,
  LoginRequest,
  LoginResponseData,
  LogoutRequest,
  RefreshTokenRequest,
  RefreshTokenResponseData,
  RegisterRequest,
  RegisterResponseData,
} from "@/features/auth/types/authTypes";

function unwrapData<T>(envelope: ApiEnvelope<T>, fallbackMessage: string) {
  if (!envelope.ok || !envelope.data) {
    throw new Error(envelope.error?.message ?? fallbackMessage);
  }
  return envelope.data;
}

export async function login(payload: LoginRequest) {
  const response = await httpClient.post<ApiEnvelope<LoginResponseData>>(
    "/v1/auth/login",
    payload
  );

  return unwrapData(response.data, "Login failed");
}

export async function register(payload: RegisterRequest) {
  const response = await httpClient.post<ApiEnvelope<RegisterResponseData>>(
    "/v1/auth/register",
    payload
  );

  return unwrapData(response.data, "Register failed");
}

export async function getMe() {
  const response = await httpClient.get<ApiEnvelope<AuthUser>>("/v1/auth/me");
  return unwrapData(response.data, "Unable to load profile");
}

export async function refreshToken(payload: RefreshTokenRequest) {
  const response = await axios.post<ApiEnvelope<RefreshTokenResponseData>>(
    `${env.apiBaseUrl}/v1/auth/refresh`,
    payload,
    {
      headers: {
        "Content-Type": "application/json",
      },
    }
  );

  return unwrapData(response.data, "Unable to refresh token");
}

export async function logout(payload: LogoutRequest) {
  const response = await httpClient.post<ApiEnvelope<Record<string, unknown>>>(
    "/v1/auth/logout",
    payload
  );

  if (!response.data.ok) {
    throw new Error(response.data.error?.message ?? "Logout failed");
  }

  return response.data.data;
}

export function extractAuthErrorMessage(error: unknown) {
  const axiosError = error as AxiosError<ApiEnvelope<null>> | undefined;
  const serverMessage = axiosError?.response?.data?.error?.message;

  if (typeof serverMessage === "string" && serverMessage.length > 0) {
    return serverMessage;
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "Request failed. Please try again.";
}
