"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { type Workflow, listWorkflows } from "@/lib/api";
import { STEP_TYPE_META } from "@/lib/constants";

export default function WorkflowsPage() {
  const [state, setState] = useState<
    | { kind: "loading" }
    | { kind: "ready"; items: Workflow[] }
    | { kind: "error"; message: string }
  >({ kind: "loading" });

  useEffect(() => {
    let active = true;
    listWorkflows()
      .then((res) => active && setState({ kind: "ready", items: res.items }))
      .catch(
        (err: unknown) =>
          active &&
          setState({
            kind: "error",
            message: err instanceof Error ? err.message : "Failed to load workflows",
          }),
      );
    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Workflows</h1>
        <Link href="/" className="text-sm underline underline-offset-2">
          + New task
        </Link>
      </div>

      {state.kind === "loading" && <p className="text-black/60 dark:text-white/60">Loading…</p>}
      {state.kind === "error" && <p className="text-red-600 dark:text-red-300">{state.message}</p>}
      {state.kind === "ready" && state.items.length === 0 && (
        <p className="text-black/60 dark:text-white/60">
          No workflows yet — create one from the <Link href="/" className="underline">home page</Link>.
        </p>
      )}
      {state.kind === "ready" && state.items.length > 0 && (
        <ul className="space-y-3">
          {state.items.map((wf) => (
            <li key={wf.id}>
              <Link
                href={`/workflows/${wf.id}`}
                className="block rounded-lg border border-black/10 p-4 hover:bg-black/[0.03] dark:border-white/10 dark:hover:bg-white/[0.05]"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium">{wf.title}</span>
                  <span className="text-xs text-black/50 dark:text-white/50">{wf.status}</span>
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {[...wf.steps]
                    .sort((a, b) => a.order_index - b.order_index)
                    .map((s) => (
                      <span
                        key={s.id}
                        className={`rounded-full px-2 py-0.5 text-xs ${STEP_TYPE_META[s.type]?.badge ?? ""}`}
                      >
                        {STEP_TYPE_META[s.type]?.label ?? s.type}
                      </span>
                    ))}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
