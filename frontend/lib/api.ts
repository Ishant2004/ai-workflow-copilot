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
    throw new ApiError(res.status, await extractError(res, path));
  }
  return (await res.json()) as T;
}

/** Prefer FastAPI's `{ "detail": ... }` message when present. */
async function extractError(res: Response, path: string): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // non-JSON body; fall through to a generic message
  }
  return `Request to ${path} failed (${res.status})`;
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

export type StepType =
  | "web_search"
  | "scrape"
  | "retrieve"
  | "summarize"
  | "notify_slack"
  | "notify_email";

export interface PlannedStep {
  type: StepType;
  name: string;
  description: string;
  config: Record<string, unknown>;
}

export interface WorkflowPlan {
  title: string;
  summary: string;
  steps: PlannedStep[];
}

export interface WorkflowStep extends PlannedStep {
  id: string;
  order_index: number;
}

export interface Workflow {
  id: string;
  title: string;
  description: string;
  status: string;
  schedule_cron?: string | null;
  created_at: string;
  updated_at: string;
  steps: WorkflowStep[];
}

/** Generate a structured plan from a task description (no persistence). */
export function previewPlan(taskDescription: string): Promise<WorkflowPlan> {
  return apiFetch<WorkflowPlan>("/api/planner/preview", {
    method: "POST",
    body: JSON.stringify({ task_description: taskDescription }),
  });
}

/** Persist a workflow — reuses an already-previewed plan to avoid a second LLM call. */
export function createWorkflow(
  taskDescription: string,
  plan?: WorkflowPlan,
): Promise<Workflow> {
  return apiFetch<Workflow>("/api/workflows", {
    method: "POST",
    body: JSON.stringify({ task_description: taskDescription, plan }),
  });
}

export interface WorkflowListResponse {
  items: Workflow[];
  total: number;
  limit: number;
  offset: number;
}

export function listWorkflows(): Promise<WorkflowListResponse> {
  return apiFetch<WorkflowListResponse>("/api/workflows");
}

export function getWorkflow(id: string): Promise<Workflow> {
  return apiFetch<Workflow>(`/api/workflows/${id}`);
}

/** A step as edited in the visual editor (no id/order — order is list position). */
export interface StepInput {
  type: StepType;
  name: string;
  description?: string | null;
  config: Record<string, unknown>;
}

export interface WorkflowPatch {
  title?: string;
  status?: string;
  schedule_cron?: string | null;
  steps?: StepInput[];
}

export function updateWorkflow(id: string, patch: WorkflowPatch): Promise<Workflow> {
  return apiFetch<Workflow>(`/api/workflows/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}
