import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, getHealth } from "@/lib/api";
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
});
