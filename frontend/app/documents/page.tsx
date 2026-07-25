"use client";

/** Document library for RAG: upload files, list them, delete them. */
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import {
  type DocumentSummary,
  deleteDocument,
  listDocuments,
  uploadDocument,
} from "@/lib/api";

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let active = true;
    listDocuments()
      .then((res) => active && setDocs(res.items))
      .catch(() => active && setError("Failed to load documents"))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  async function onUpload(file: File) {
    setUploading(true);
    setError(null);
    try {
      const doc = await uploadDocument(file);
      setDocs((prev) => [doc, ...prev]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function onDelete(id: string) {
    const prev = docs;
    setDocs((d) => d.filter((doc) => doc.id !== id)); // optimistic
    try {
      await deleteDocument(id);
    } catch {
      setDocs(prev); // roll back on failure
      setError("Delete failed");
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Documents</h1>
        <Link href="/workflows" className="text-sm underline underline-offset-2">
          Workflows
        </Link>
      </div>
      <p className="text-sm text-black/60 dark:text-white/60">
        Upload documents to ground your workflows. A <code>retrieve</code> step pulls the most
        relevant chunks into a run.
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <input
          ref={fileInput}
          type="file"
          aria-label="Upload document"
          accept=".txt,.md,.pdf,text/plain,application/pdf"
          disabled={uploading}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void onUpload(file);
          }}
          className="text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-foreground file:px-4 file:py-2 file:text-sm file:font-medium file:text-background hover:file:opacity-90"
        />
        {uploading && <span className="text-sm text-black/60 dark:text-white/60">Uploading…</span>}
      </div>
      {error && <p className="text-sm text-red-600 dark:text-red-300">{error}</p>}

      {loading ? (
        <p className="text-sm text-black/60 dark:text-white/60">Loading…</p>
      ) : docs.length === 0 ? (
        <p className="text-sm text-black/60 dark:text-white/60">
          No documents yet. Upload a .txt, .md, or .pdf to get started.
        </p>
      ) : (
        <ul className="space-y-3">
          {docs.map((doc) => (
            <li
              key={doc.id}
              className="flex items-center justify-between gap-3 rounded-lg border border-black/10 p-4 dark:border-white/10"
            >
              <div className="min-w-0">
                <p className="truncate font-medium">{doc.filename}</p>
                <p className="text-xs text-black/50 dark:text-white/50">
                  {doc.chunk_count} chunk{doc.chunk_count === 1 ? "" : "s"} ·{" "}
                  {Math.max(1, Math.round(doc.size_bytes / 1024))} KB
                </p>
              </div>
              <button
                type="button"
                onClick={() => void onDelete(doc.id)}
                aria-label={`Delete ${doc.filename}`}
                className="rounded-lg border border-red-500/40 px-3 py-1.5 text-sm text-red-600 hover:bg-red-500/5 dark:text-red-300"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
