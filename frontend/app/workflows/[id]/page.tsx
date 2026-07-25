"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { FeedbackButtons } from "@/app/components/FeedbackButtons";
import { RunsPanel } from "@/app/components/workflow/RunsPanel";
import { WorkflowEditor } from "@/app/components/workflow/WorkflowEditor";
import { type Workflow, getWorkflow } from "@/lib/api";

export default function WorkflowEditorPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [state, setState] = useState<
    { kind: "loading" } | { kind: "ready"; workflow: Workflow } | { kind: "error"; message: string }
  >({ kind: "loading" });

  useEffect(() => {
    let active = true;
    getWorkflow(id)
      .then((workflow) => active && setState({ kind: "ready", workflow }))
      .catch(
        (err: unknown) =>
          active &&
          setState({
            kind: "error",
            message: err instanceof Error ? err.message : "Failed to load workflow",
          }),
      );
    return () => {
      active = false;
    };
  }, [id]);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center gap-6 px-6 py-10">
      {state.kind === "loading" && <p className="text-black/60 dark:text-white/60">Loading…</p>}
      {state.kind === "error" && (
        <p className="text-red-600 dark:text-red-300">{state.message}</p>
      )}
      {state.kind === "ready" && (
        <>
          <WorkflowEditor workflow={state.workflow} />
          <FeedbackButtons workflowId={state.workflow.id} />
          <RunsPanel workflow={state.workflow} />
        </>
      )}
    </main>
  );
}
