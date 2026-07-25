import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DocumentsPage from "@/app/documents/page";
import { FeedbackButtons } from "@/app/components/FeedbackButtons";
import { deleteDocument, uploadDocument } from "@/lib/api";
import { config } from "@/lib/config";

afterEach(() => {
  vi.restoreAllMocks();
});

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

const doc = {
  id: "d1",
  filename: "notes.txt",
  content_type: "text/plain",
  size_bytes: 2048,
  chunk_count: 3,
  created_at: new Date().toISOString(),
};

describe("documents API client", () => {
  it("uploads as multipart (no JSON content-type) to /api/documents", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(doc, 201));
    const file = new File(["hello"], "notes.txt", { type: "text/plain" });

    await uploadDocument(file);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${config.apiBaseUrl}/api/documents`);
    expect((init as RequestInit).method).toBe("POST");
    expect((init as RequestInit).body).toBeInstanceOf(FormData);
    // Multipart must NOT force application/json (browser sets the boundary).
    expect((init as RequestInit).headers).toBeUndefined();
  });

  it("deletes without parsing a body (204)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    await expect(deleteDocument("d1")).resolves.toBeUndefined();
  });
});

describe("DocumentsPage", () => {
  it("lists documents and uploads a new one", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ items: [], total: 0, limit: 20, offset: 0 })) // list
      .mockResolvedValueOnce(jsonResponse(doc, 201)); // upload

    render(<DocumentsPage />);
    await waitFor(() => expect(screen.getByText(/No documents yet/i)).toBeInTheDocument());

    const file = new File(["hello"], "notes.txt", { type: "text/plain" });
    fireEvent.change(screen.getByLabelText(/Upload document/i), { target: { files: [file] } });

    await waitFor(() => expect(screen.getByText("notes.txt")).toBeInTheDocument());
    expect(screen.getByText(/3 chunks/i)).toBeInTheDocument();
    expect(fetchMock.mock.calls[1][0]).toContain("/api/documents");
  });
});

describe("FeedbackButtons", () => {
  it("submits positive feedback and thanks the user", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ id: "f1", workflow_id: "wf1", rating: "positive", comment: null, created_at: "" }, 201),
    );

    render(<FeedbackButtons workflowId="wf1" />);
    fireEvent.click(screen.getByRole("button", { name: /Good suggestion/i }));

    await waitFor(() => expect(screen.getByText(/Thanks for the feedback/i)).toBeInTheDocument());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/workflows/wf1/feedback");
    expect(JSON.parse((init as RequestInit).body as string)).toMatchObject({ rating: "positive" });
  });
});
