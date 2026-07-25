import type { RunStatus, StepType } from "./api";

/** Max task length — mirrors the backend's `task_description` limit. */
export const TASK_MAX_LENGTH = 4000;

/** Example task shown via the "Try an example" affordance. */
export const EXAMPLE_TASK =
  "Every morning, collect the latest AI startup news, summarize it, and send me a digest on Slack.";

/** Per-step-type label + Tailwind badge classes (light/dark aware). */
export const STEP_TYPE_META: Record<StepType, { label: string; badge: string }> = {
  web_search: {
    label: "Web search",
    badge: "bg-blue-500/15 text-blue-600 dark:text-blue-300",
  },
  scrape: {
    label: "Scrape",
    badge: "bg-purple-500/15 text-purple-600 dark:text-purple-300",
  },
  retrieve: {
    label: "Retrieve (docs)",
    badge: "bg-indigo-500/15 text-indigo-600 dark:text-indigo-300",
  },
  summarize: {
    label: "Summarize",
    badge: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  },
  notify_slack: {
    label: "Slack",
    badge: "bg-green-500/15 text-green-600 dark:text-green-300",
  },
  notify_email: {
    label: "Email",
    badge: "bg-teal-500/15 text-teal-600 dark:text-teal-300",
  },
};

/** All step types, in a sensible authoring order (for the editor's type picker). */
export const STEP_TYPES = Object.keys(STEP_TYPE_META) as StepType[];

const GRAY = "bg-black/10 text-black/60 dark:bg-white/10 dark:text-white/60";

/** Run-status label + badge classes. */
export const RUN_STATUS_META: Record<RunStatus, { label: string; badge: string }> = {
  pending: { label: "Pending", badge: GRAY },
  running: { label: "Running", badge: "bg-blue-500/15 text-blue-600 dark:text-blue-300" },
  awaiting_review: {
    label: "Awaiting review",
    badge: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  },
  succeeded: { label: "Succeeded", badge: "bg-green-500/15 text-green-600 dark:text-green-300" },
  failed: { label: "Failed", badge: "bg-red-500/15 text-red-600 dark:text-red-300" },
  rejected: { label: "Rejected", badge: GRAY },
};
