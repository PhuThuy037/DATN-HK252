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
