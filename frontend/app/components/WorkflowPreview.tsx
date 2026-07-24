import type { PlannedStep, WorkflowPlan } from "@/lib/api";
import { STEP_TYPE_META } from "@/lib/constants";

function StepCard({ step, index }: { step: PlannedStep; index: number }) {
  const meta = STEP_TYPE_META[step.type] ?? {
    label: step.type,
    badge: "bg-gray-500/15 text-gray-600 dark:text-gray-300",
  };
  const configEntries = Object.entries(step.config ?? {});

  return (
    <li className="flex gap-4 rounded-lg border border-black/10 bg-black/[0.02] p-4 dark:border-white/10 dark:bg-white/[0.03]">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-black/10 text-sm font-medium dark:bg-white/10">
        {index + 1}
      </div>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${meta.badge}`}>
            {meta.label}
          </span>
          <span className="font-medium">{step.name}</span>
        </div>
        {step.description && (
          <p className="text-sm text-black/60 dark:text-white/60">{step.description}</p>
        )}
        {configEntries.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {configEntries.map(([key, value]) => (
              <span
                key={key}
                className="rounded bg-black/5 px-1.5 py-0.5 font-mono text-xs text-black/70 dark:bg-white/10 dark:text-white/70"
                title={String(value)}
              >
                {key}: {String(value)}
              </span>
            ))}
          </div>
        )}
      </div>
    </li>
  );
}

export function WorkflowPreview({ plan }: { plan: WorkflowPlan }) {
  return (
    <section className="space-y-4 text-left" aria-label="Generated workflow">
      <header className="space-y-1">
        <h2 className="text-xl font-semibold">{plan.title}</h2>
        <p className="text-sm text-black/60 dark:text-white/60">{plan.summary}</p>
      </header>
      <ol className="space-y-3">
        {plan.steps.map((step, i) => (
          <StepCard key={i} step={step} index={i} />
        ))}
      </ol>
    </section>
  );
}
