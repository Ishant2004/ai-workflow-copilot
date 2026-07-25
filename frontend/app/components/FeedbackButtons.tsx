"use client";

/**
 * 👍 / 👎 on a workflow's suggestion. Positive feedback becomes a planning exemplar
 * that steers future suggestions (the backend's learning loop).
 */
import { useState } from "react";

import { type FeedbackRating, submitFeedback } from "@/lib/api";

export function FeedbackButtons({ workflowId }: { workflowId: string }) {
  const [state, setState] = useState<
    { kind: "idle" } | { kind: "sending" } | { kind: "done"; rating: FeedbackRating } | { kind: "error"; message: string }
  >({ kind: "idle" });

  async function send(rating: FeedbackRating) {
    setState({ kind: "sending" });
    try {
      await submitFeedback(workflowId, rating);
      setState({ kind: "done", rating });
    } catch (err) {
      setState({ kind: "error", message: err instanceof Error ? err.message : "Failed" });
    }
  }

  if (state.kind === "done") {
    return (
      <p className="text-sm text-black/60 dark:text-white/60">
        Thanks for the feedback {state.rating === "positive" ? "👍" : "👎"}
      </p>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-black/60 dark:text-white/60">Was this a good suggestion?</span>
      <button
        type="button"
        onClick={() => void send("positive")}
        disabled={state.kind === "sending"}
        aria-label="Good suggestion"
        className="rounded-lg border border-black/15 px-3 py-1.5 text-sm hover:bg-green-500/10 disabled:opacity-40 dark:border-white/15"
      >
        👍 Good
      </button>
      <button
        type="button"
        onClick={() => void send("negative")}
        disabled={state.kind === "sending"}
        aria-label="Bad suggestion"
        className="rounded-lg border border-black/15 px-3 py-1.5 text-sm hover:bg-red-500/10 disabled:opacity-40 dark:border-white/15"
      >
        👎 Bad
      </button>
      {state.kind === "error" && (
        <span className="text-sm text-red-600 dark:text-red-300">{state.message}</span>
      )}
    </div>
  );
}
