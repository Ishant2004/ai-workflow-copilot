import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TaskComposer } from "@/app/components/TaskComposer";

afterEach(() => {
  vi.restoreAllMocks();
});

const PLAN = {
  title: "Morning AI digest",
  summary: "Collect, summarize, notify.",
  steps: [
    { type: "web_search", name: "Search", description: "Find news", config: { query: "ai" } },
    { type: "notify_slack", name: "Notify", description: "Send it", config: {} },
  ],
};

function mockJson(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

describe("TaskComposer", () => {
  it("generates and renders the workflow steps", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJson(PLAN));

    render(<TaskComposer />);
    fireEvent.change(screen.getByLabelText(/describe your task/i), {
      target: { value: "collect ai news" },
    });
    fireEvent.click(screen.getByRole("button", { name: /generate workflow/i }));

    await waitFor(() =>
      expect(screen.getByText("Morning AI digest")).toBeInTheDocument(),
    );
    // both step names render, in order
    expect(screen.getByText("Search")).toBeInTheDocument();
    expect(screen.getByText("Notify")).toBeInTheDocument();
    // step-type badge + config pill
    expect(screen.getByText("Web search")).toBeInTheDocument();
    expect(screen.getByText(/query: ai/)).toBeInTheDocument();
  });

  it("shows the backend error detail when generation fails", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockJson({ detail: "LLM request failed" }, 502),
    );

    render(<TaskComposer />);
    fireEvent.change(screen.getByLabelText(/describe your task/i), {
      target: { value: "x" },
    });
    fireEvent.click(screen.getByRole("button", { name: /generate workflow/i }));

    await waitFor(() =>
      expect(screen.getByText("LLM request failed")).toBeInTheDocument(),
    );
  });

  it("disables generate when the task is empty", () => {
    render(<TaskComposer />);
    expect(screen.getByRole("button", { name: /generate workflow/i })).toBeDisabled();
  });
});
