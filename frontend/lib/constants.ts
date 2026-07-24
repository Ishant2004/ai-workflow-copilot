import type { StepType } from "./api";

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
