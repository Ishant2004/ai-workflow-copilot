/**
 * Typed client for the Workflow AI Copilot backend.
 *
 * A thin wrapper over fetch that targets `config.apiBaseUrl` and raises a typed
 * error on non-2xx responses. Endpoint-specific helpers build on `apiFetch`.
 */
import { config } from "./config";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${config.apiBaseUrl}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    throw new ApiError(res.status, `Request to ${path} failed (${res.status})`);
  }
  return (await res.json()) as T;
}

// --- Endpoint types & helpers ---

export interface Health {
  status: string;
  app: string;
  env: string;
  version: string;
}

export function getHealth(): Promise<Health> {
  return apiFetch<Health>("/health");
}
