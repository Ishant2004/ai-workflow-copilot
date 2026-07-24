import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BackendStatus } from "@/app/components/BackendStatus";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("BackendStatus", () => {
  it("shows the backend as online once /health resolves", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ status: "ok", app: "x", env: "development", version: "0.1.0" }),
        { status: 200 },
      ),
    );

    render(<BackendStatus />);

    await waitFor(() =>
      expect(screen.getByText(/Backend online/i)).toBeInTheDocument(),
    );
    expect(screen.getByText(/development/)).toBeInTheDocument();
  });

  it("shows unreachable when /health fails", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("x", { status: 500 }));

    render(<BackendStatus />);

    await waitFor(() =>
      expect(screen.getByText(/Backend unreachable/i)).toBeInTheDocument(),
    );
  });
});
