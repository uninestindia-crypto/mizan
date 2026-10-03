// Fetch wrapper for the local QuantOS engine: CSRF on writes, typed errors from the error envelope.

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
    public readonly details: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let csrfToken: string | null = null;

async function csrf(refresh = false): Promise<string> {
  if (csrfToken && !refresh) return csrfToken;
  const res = await fetch("/api/v1/csrf-token", { headers: { Accept: "application/json" } });
  if (!res.ok) throw new ApiError("CSRF_UNAVAILABLE", "Could not start a secure session with the engine.", res.status);
  const body = (await res.json()) as { csrf_token: string };
  csrfToken = body.csrf_token;
  return csrfToken;
}

type Method = "GET" | "POST" | "PUT" | "DELETE";

export async function api<T>(path: string, method: Method = "GET", body?: unknown): Promise<T> {
  return request<T>(path, method, body, true);
}

async function request<T>(path: string, method: Method, body: unknown, retry: boolean): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") {
    headers["X-CSRF-Token"] = await csrf();
    if (body !== undefined) headers["Content-Type"] = "application/json";
  }
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("ENGINE_OFFLINE", "The QuantOS engine is not responding.", 0);
  }
  if (res.status === 403 && method !== "GET" && retry) {
    await csrf(true);
    return request<T>(path, method, body, false);
  }
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    const envelope = (data as { error?: { code?: string; message?: string; details?: unknown } } | null)?.error;
    throw new ApiError(
      envelope?.code ?? `HTTP_${res.status}`,
      envelope?.message ?? (res.statusText || "Request failed"),
      res.status,
      envelope?.details ?? null,
    );
  }
  return data as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}
