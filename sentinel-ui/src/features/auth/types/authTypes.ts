export type ApiError = {
  code: string;
  message: string;
  details?: unknown[];
};

export type ApiEnvelope<T> = {
  ok: boolean;
  data: T | null;
  error: ApiError | null;
  meta?: Record<string, unknown>;
};

export type AuthUser = {
  id: string;
  email: string;
  name: string;
  status: string;
};

export type LoginRequest = {
  email: string;
  password: string;
};

export type LoginResponseData = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: AuthUser;
};

export type RegisterRequest = {
  email: string;
  password: string;
  name: string;
};

export type RegisterResponseData = {
  user: AuthUser;
};

export type LogoutRequest = {
  refresh_token: string;
};

export type RefreshTokenRequest = {
  refresh_token: string;
};

export type RefreshTokenResponseData = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
};
