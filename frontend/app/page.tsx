import { BackendStatus } from "@/app/components/BackendStatus";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-8 px-6 py-16 text-center">
      <div className="max-w-2xl space-y-4">
        <p className="text-sm font-medium uppercase tracking-widest text-black/50 dark:text-white/50">
          Workflow AI Copilot
        </p>
        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
          Describe a task. Get a runnable workflow.
        </h1>
        <p className="text-lg text-black/70 dark:text-white/70">
          Type a repetitive task in plain English — the copilot breaks it into
          steps, runs parts of it, and learns from your feedback.
        </p>
      </div>

      {/* Placeholder for the task-input experience (Step 8). */}
      <div className="w-full max-w-xl rounded-xl border border-dashed border-black/15 dark:border-white/20 p-8 text-black/50 dark:text-white/50">
        Task input &amp; workflow preview arrive in the next step.
      </div>

      <BackendStatus />
    </main>
  );
}
