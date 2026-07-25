import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RunsPanel } from "@/app/components/workflow/RunsPanel";
import type { Run, Workflow } from "@/lib/api";

afterEach(() => {
  vi.restoreAllMocks();
});

const workflow: Workflow = {
  id: "wf1",
  title: "Test",
  description: "d",
  status: "draft",
  schedule_cron: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  steps: [
    { id: "s1", order_index: 0, type: "web_search", name: "Search", description: "", config: {} },
    { id: "s2", order_index: 1, type: "summarize", name: "Summarize", description: "", config: {} },
    { id: "s3", order_index: 2, type: "notify_slack", name: "Notify", description: "", config: {} },
  ],
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function awaitingRun(): Run {
  return {
    id: "run1",
    workflow_id: "wf1",
    status: "awaiting_review",
    started_at: null,
    finished_at: null,
    error: null,
    created_at: new Date().toISOString(),
    step_results: [
      {
        id: "sr1",
        step_id: "s1",
        status: "succeeded",
        output: { count: 2 },
        error: null,
        started_at: null,
        finished_at: null,
        created_at: new Date().toISOString(),
      },
      {
        id: "sr2",
        step_id: "s2",
        status: "succeeded",
        output: { summary: "the digest" },
        error: null,
        started_at: null,
        finished_at: null,
        created_at: new Date().toISOString(),
      },
    ],
  };
}

describe("RunsPanel", () => {
  it("shows empty state when there are no runs", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([]));
    render(<RunsPanel workflow={workflow} />);
    await waitFor(() => expect(screen.getByText(/No runs yet/i)).toBeInTheDocument());
  });

  it("runs the workflow and renders review controls when it pauses for review", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([])) // initial listRuns
      .mockResolvedValueOnce(jsonResponse(awaitingRun())); // runWorkflow

    render(<RunsPanel workflow={workflow} />);
    await waitFor(() => expect(screen.getByText(/No runs yet/i)).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /Run workflow/i }));

    await waitFor(() => expect(screen.getByText(/Awaiting review/i)).toBeInTheDocument());
    // The reviewable summary output is shown (preview + editable textarea), with approve/reject.
    expect(screen.getAllByText(/the digest/).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /Approve & continue/i })).toBeInTheDocument();

    // The POST run call hit the right endpoint.
    const runCall = fetchMock.mock.calls[1][0] as string;
    expect(runCall).toContain("/api/workflows/wf1/runs");
  });

  it("approves a paused run", async () => {
    const succeeded = { ...awaitingRun(), status: "succeeded" as const };
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([awaitingRun()])) // listRuns → already awaiting
      .mockResolvedValueOnce(jsonResponse(succeeded)); // approveRun

    render(<RunsPanel workflow={workflow} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Approve & continue/i })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: /Approve & continue/i }));

    await waitFor(() => expect(screen.getByText(/Succeeded/i)).toBeInTheDocument());
    const approveCall = fetchMock.mock.calls[1][0] as string;
    expect(approveCall).toContain("/api/runs/run1/approve");
  });
});
