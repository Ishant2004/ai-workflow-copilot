"use client";

/**
 * Run a workflow and view its history + results, including the human-in-the-loop
 * review gate (edit output → approve/reject) for runs paused at `awaiting_review`.
 */
import { useEffect, useState } from "react";

import {
  type Run,
  type StepResult,
  type Workflow,
  approveRun,
  editStepResult,
  listRuns,
  rejectRun,
  runWorkflow,
} from "@/lib/api";
import { RUN_STATUS_META, STEP_TYPE_META } from "@/lib/constants";

export function RunsPanel({ workflow }: { workflow: Workflow }) {
  const stepMeta = new Map(workflow.steps.map((s) => [s.id, s]));
  const [runs, setRuns] = useState<Run[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listRuns(workflow.id)
      .then((rs) => active && setRuns(rs))
      .catch(() => active && setRuns([]));
    return () => {
      active = false;
    };
  }, [workflow.id]);

  /** Replace a run in the list by id (after a review action), or prepend a new one. */
  function upsert(run: Run) {
    setRuns((prev) => {
      const i = prev.findIndex((r) => r.id === run.id);
      if (i === -1) return [run, ...prev];
      const next = [...prev];
      next[i] = run;
      return next;
    });
  }

  async function onRun() {
    setRunning(true);
    setError(null);
    try {
      upsert(await runWorkflow(workflow.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Run failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <section className="flex w-full flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Runs</h2>
        <button
          type="button"
          onClick={onRun}
          disabled={running}
          className="rounded-lg bg-foreground px-4 py-2 text-sm font-medium text-background hover:opacity-90 disabled:opacity-40"
        >
          {running ? "Running…" : "▶ Run workflow"}
        </button>
      </div>
      {error && <p className="text-sm text-red-600 dark:text-red-300">{error}</p>}
      {runs.length === 0 ? (
        <p className="text-sm text-black/60 dark:text-white/60">
          No runs yet. Run the workflow to see results here.
        </p>
      ) : (
        <ol className="flex flex-col gap-3">
          {runs.map((run) => (
            <RunCard key={run.id} run={run} stepMeta={stepMeta} onChange={upsert} />
          ))}
        </ol>
      )}
    </section>
  );
}

function RunCard({
  run,
  stepMeta,
  onChange,
}: {
  run: Run;
  stepMeta: Map<string, Workflow["steps"][number]>;
  onChange: (run: Run) => void;
}) {
  const meta = RUN_STATUS_META[run.status];
  return (
    <li className="rounded-xl border border-black/10 p-4 dark:border-white/10">
      <div className="flex items-center justify-between">
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${meta.badge}`}>
          {meta.label}
        </span>
        <time className="text-xs text-black/50 dark:text-white/50">
          {new Date(run.created_at).toLocaleString()}
        </time>
      </div>

      <ol className="mt-3 flex flex-col gap-2">
        {run.step_results.map((sr) => (
          <StepResultRow key={sr.id} result={sr} stepMeta={stepMeta} />
        ))}
      </ol>

      {run.error && <p className="mt-2 text-sm text-red-600 dark:text-red-300">{run.error}</p>}

      {run.status === "awaiting_review" && <ReviewControls run={run} onChange={onChange} />}
    </li>
  );
}

function StepResultRow({
  result,
  stepMeta,
}: {
  result: StepResult;
  stepMeta: Map<string, Workflow["steps"][number]>;
}) {
  const step = stepMeta.get(result.step_id);
  const typeMeta = step ? STEP_TYPE_META[step.type] : undefined;
  const ok = result.status === "succeeded";
  return (
    <li className="flex items-start gap-2 text-sm">
      <span aria-hidden className={ok ? "text-green-600 dark:text-green-400" : "text-black/40"}>
        {ok ? "✓" : result.status === "failed" ? "✗" : "•"}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {typeMeta && (
            <span className={`rounded-full px-2 py-0.5 text-xs ${typeMeta.badge}`}>
              {typeMeta.label}
            </span>
          )}
          <span className="text-black/70 dark:text-white/70">{step?.name ?? "step"}</span>
        </div>
        {result.output != null && (
          <p className="mt-1 whitespace-pre-wrap break-words text-black/60 dark:text-white/60">
            {outputPreview(result.output)}
          </p>
        )}
        {result.error && <p className="mt-1 text-red-600 dark:text-red-300">{result.error}</p>}
      </div>
    </li>
  );
}

function ReviewControls({ run, onChange }: { run: Run; onChange: (run: Run) => void }) {
  // The step to review is the last produced output before the paused side-effect.
  const reviewable = [...run.step_results].reverse().find((r) => r.output != null);
  const [draft, setDraft] = useState(() =>
    reviewable ? JSON.stringify(reviewable.output, null, 2) : "",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function act(fn: () => Promise<Run>) {
    setBusy(true);
    setError(null);
    try {
      onChange(await fn());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  async function onSaveEdit() {
    if (!reviewable) return;
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(draft);
    } catch {
      setError("Output must be valid JSON");
      return;
    }
    await act(() => editStepResult(run.id, reviewable.id, parsed));
  }

  return (
    <div className="mt-3 flex flex-col gap-2 rounded-lg bg-amber-500/5 p-3">
      <p className="text-sm font-medium">Review before it sends</p>
      {reviewable && (
        <textarea
          aria-label="Edit output"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={5}
          className="w-full rounded-md border border-black/15 bg-transparent p-2 font-mono text-xs dark:border-white/15"
        />
      )}
      <div className="flex flex-wrap items-center gap-2">
        {reviewable && (
          <button
            type="button"
            onClick={onSaveEdit}
            disabled={busy}
            className="rounded-lg border border-black/15 px-3 py-1.5 text-sm hover:bg-black/[0.03] disabled:opacity-40 dark:border-white/15 dark:hover:bg-white/[0.05]"
          >
            Save edit
          </button>
        )}
        <button
          type="button"
          onClick={() => act(() => approveRun(run.id))}
          disabled={busy}
          className="rounded-lg bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40"
        >
          Approve &amp; continue
        </button>
        <button
          type="button"
          onClick={() => act(() => rejectRun(run.id))}
          disabled={busy}
          className="rounded-lg border border-red-500/40 px-3 py-1.5 text-sm text-red-600 hover:bg-red-500/5 disabled:opacity-40 dark:text-red-300"
        >
          Reject
        </button>
        {error && <span className="text-sm text-red-600 dark:text-red-300">{error}</span>}
      </div>
    </div>
  );
}

/** Human-friendly preview of a step's output; falls back to compact JSON. */
function outputPreview(output: Record<string, unknown>): string {
  for (const key of ["summary", "final", "message_preview", "note"]) {
    const v = output[key];
    if (typeof v === "string" && v) return v;
  }
  if (typeof output.count === "number") return `${output.count} result(s)`;
  const json = JSON.stringify(output);
  return json.length > 300 ? `${json.slice(0, 300)}…` : json;
}
