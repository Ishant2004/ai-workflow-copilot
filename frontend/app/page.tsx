import Link from "next/link";

import { BackendStatus } from "@/app/components/BackendStatus";
import { TaskComposer } from "@/app/components/TaskComposer";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="flex items-center justify-between border-b border-black/10 px-6 py-4 dark:border-white/10">
        <span className="text-sm font-semibold tracking-tight">
          Workflow AI Copilot
        </span>
        <div className="flex items-center gap-4">
          <Link href="/workflows" className="text-sm underline underline-offset-2">
            Workflows
          </Link>
          <BackendStatus />
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center gap-10 px-6 py-12">
        <div className="max-w-2xl space-y-3 text-center">
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Describe a task. Get a runnable workflow.
          </h1>
          <p className="text-black/70 dark:text-white/70">
            The copilot breaks your plain-English task into ordered, typed steps.
          </p>
        </div>

        <TaskComposer />
      </main>
    </div>
  );
}
