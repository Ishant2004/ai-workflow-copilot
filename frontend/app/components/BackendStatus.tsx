"use client";

import { useEffect, useState } from "react";

import { getHealth, type Health } from "@/lib/api";

type State =
  | { kind: "loading" }
  | { kind: "ok"; health: Health }
  | { kind: "error"; message: string };

/** Small live indicator that the frontend can reach the backend API. */
export function BackendStatus() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let active = true;
    getHealth()
      .then((health) => active && setState({ kind: "ok", health }))
      .catch(
        (err: unknown) =>
          active &&
          setState({
            kind: "error",
            message: err instanceof Error ? err.message : "Unknown error",
          }),
      );
    return () => {
      active = false;
    };
  }, []);

  const dot =
    state.kind === "ok"
      ? "bg-green-500"
      : state.kind === "error"
        ? "bg-red-500"
        : "bg-amber-400 animate-pulse";

  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-black/10 dark:border-white/15 px-3 py-1 text-sm">
      <span className={`h-2.5 w-2.5 rounded-full ${dot}`} aria-hidden />
      {state.kind === "loading" && <span>Checking backend…</span>}
      {state.kind === "ok" && (
        <span>
          Backend online · <span className="font-mono">{state.health.env}</span> ·
          v{state.health.version}
        </span>
      )}
      {state.kind === "error" && <span>Backend unreachable ({state.message})</span>}
    </div>
  );
}
