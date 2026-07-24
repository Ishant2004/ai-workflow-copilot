import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, createWorkflow, getHealth, previewPlan } from "@/lib/api";
import { config } from "@/lib/config";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("config", () => {
  it("defaults the API base URL to localhost", () => {
    expect(config.apiBaseUrl).toContain("://");
  });
});

describe("apiFetch", () => {
  it("targets the configured base URL and parses JSON", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
      );

    const data = await apiFetch<{ status: string }>("/health");

    expect(data.status).toBe("ok");
    expect(fetchMock).toHaveBeenCalledWith(
      `${config.apiBaseUrl}/health`,
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });

  it("throws a typed ApiError on non-2xx responses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("nope", { status: 503 }),
    );

    await expect(getHealth()).rejects.toBeInstanceOf(ApiError);
    await expect(getHealth()).rejects.toMatchObject({ status: 503 });
  });

  it("surfaces FastAPI's detail message on errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Planner is not configured." }), {
        status: 503,
      }),
    );
    await expect(getHealth()).rejects.toMatchObject({
      message: "Planner is not configured.",
    });
  });
});

describe("workflow helpers", () => {
  it("previewPlan POSTs the task description", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ title: "t", summary: "s", steps: [] }), {
        status: 200,
      }),
    );
    const plan = await previewPlan("do a thing");
    expect(plan.title).toBe("t");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${config.apiBaseUrl}/api/planner/preview`);
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      task_description: "do a thing",
    });
  });

  it("createWorkflow POSTs the task and plan", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ id: "abc", steps: [] }), { status: 201 }),
      );
    const plan = { title: "t", summary: "s", steps: [] };
    await createWorkflow("do a thing", plan);
    const body = JSON.parse(
      (fetchMock.mock.calls[0][1] as RequestInit).body as string,
    );
    expect(body).toEqual({ task_description: "do a thing", plan });
  });
});
