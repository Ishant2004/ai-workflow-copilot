"use client";

import { useState } from "react";

import { WorkflowPreview } from "@/app/components/WorkflowPreview";
import { createWorkflow, previewPlan, type Workflow, type WorkflowPlan } from "@/lib/api";
import { EXAMPLE_TASK, TASK_MAX_LENGTH } from "@/lib/constants";

type Phase = "idle" | "generating" | "previewed";
type SaveState =
  | { kind: "none" }
  | { kind: "saving" }
  | { kind: "saved"; workflow: Workflow }
  | { kind: "error"; message: string };

export function TaskComposer() {
  const [task, setTask] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [plan, setPlan] = useState<WorkflowPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [save, setSave] = useState<SaveState>({ kind: "none" });

  const trimmed = task.trim();
  const canGenerate = trimmed.length > 0 && phase !== "generating";

  async function generate() {
    if (!canGenerate) return;
    setPhase("generating");
    setError(null);
    setSave({ kind: "none" });
    try {
      const result = await previewPlan(trimmed);
      setPlan(result);
      setPhase("previewed");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate plan");
      setPhase("idle");
    }
  }

  async function saveWorkflow() {
    if (!plan) return;
    setSave({ kind: "saving" });
    try {
      const workflow = await createWorkflow(trimmed, plan);
      setSave({ kind: "saved", workflow });
    } catch (err) {
      setSave({
        kind: "error",
        message: err instanceof Error ? err.message : "Failed to save workflow",
      });
    }
  }

  function reset() {
    setTask("");
    setPlan(null);
    setPhase("idle");
    setError(null);
    setSave({ kind: "none" });
  }

  return (
    <div className="w-full max-w-2xl space-y-6 text-left">
      <div className="space-y-2">
        <label htmlFor="task" className="block text-sm font-medium">
          Describe your task
        </label>
        <textarea
          id="task"
          value={task}
          onChange={(e) => setTask(e.target.value)}
          maxLength={TASK_MAX_LENGTH}
          rows={4}
          placeholder="e.g. Every morning, collect the latest AI startup news, summarize it, and send me a digest on Slack."
          className="w-full resize-y rounded-lg border border-black/15 bg-white px-3 py-2 text-sm outline-none focus:border-black/40 dark:border-white/15 dark:bg-white/[0.03] dark:focus:border-white/40"
        />
        <div className="flex items-center justify-between text-xs text-black/50 dark:text-white/50">
          <button
            type="button"
            onClick={() => setTask(EXAMPLE_TASK)}
            className="underline underline-offset-2 hover:text-black/80 dark:hover:text-white/80"
          >
            Try an example
          </button>
          <span>
            {task.length}/{TASK_MAX_LENGTH}
          </span>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={generate}
          disabled={!canGenerate}
          className="rounded-lg bg-foreground px-4 py-2 text-sm font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          {phase === "generating" ? "Generating…" : "Generate workflow"}
        </button>
        {phase === "previewed" && (
          <button
            type="button"
            onClick={reset}
            className="rounded-lg border border-black/15 px-4 py-2 text-sm font-medium hover:bg-black/[0.03] dark:border-white/15 dark:hover:bg-white/[0.05]"
          >
            Start over
          </button>
        )}
      </div>

      {error && (
        <p className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-600 dark:text-red-300">
          {error}
        </p>
      )}

      {phase === "previewed" && plan && (
        <div className="space-y-4">
          <WorkflowPreview plan={plan} />
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={saveWorkflow}
              disabled={save.kind === "saving" || save.kind === "saved"}
              className="rounded-lg border border-black/15 px-4 py-2 text-sm font-medium hover:bg-black/[0.03] disabled:opacity-40 dark:border-white/15 dark:hover:bg-white/[0.05]"
            >
              {save.kind === "saving"
                ? "Saving…"
                : save.kind === "saved"
                  ? "Saved ✓"
                  : "Save workflow"}
            </button>
            {save.kind === "saved" && (
              <span className="text-sm text-green-600 dark:text-green-300">
                Saved as <span className="font-mono">{save.workflow.id.slice(0, 8)}</span>
              </span>
            )}
            {save.kind === "error" && (
              <span className="text-sm text-red-600 dark:text-red-300">{save.message}</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
