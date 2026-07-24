"use client";

import {
  DndContext,
  type DragEndEvent,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import Link from "next/link";
import { useState } from "react";

import { type Workflow, updateWorkflow } from "@/lib/api";
import {
  ConfigParseError,
  type EditableStep,
  blankStep,
  fromWorkflowStep,
  move,
  toStepInput,
} from "@/lib/steps";
import { StepNode } from "@/app/components/workflow/StepNode";

type SaveState =
  | { kind: "idle" }
  | { kind: "saving" }
  | { kind: "saved" }
  | { kind: "error"; message: string };

const STATUSES = ["draft", "active", "archived"] as const;

export function WorkflowEditor({ workflow }: { workflow: Workflow }) {
  const [title, setTitle] = useState(workflow.title);
  const [status, setStatus] = useState(workflow.status);
  const [cron, setCron] = useState(workflow.schedule_cron ?? "");
  const [steps, setSteps] = useState<EditableStep[]>(
    [...workflow.steps]
      .sort((a, b) => a.order_index - b.order_index)
      .map(fromWorkflowStep),
  );
  const [save, setSave] = useState<SaveState>({ kind: "idle" });

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }));

  function patchStep(key: string, patch: Partial<EditableStep>) {
    setSteps((prev) => prev.map((s) => (s.key === key ? { ...s, ...patch } : s)));
    setSave({ kind: "idle" });
  }

  function onDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const from = steps.findIndex((s) => s.key === active.id);
    const to = steps.findIndex((s) => s.key === over.id);
    setSteps(move(steps, from, to));
  }

  async function onSave() {
    setSave({ kind: "saving" });
    try {
      const stepInputs = steps.map(toStepInput);
      await updateWorkflow(workflow.id, {
        title: title.trim() || workflow.title,
        status,
        schedule_cron: cron.trim() || null,
        steps: stepInputs,
      });
      setSave({ kind: "saved" });
    } catch (err) {
      const message =
        err instanceof ConfigParseError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Failed to save";
      setSave({ kind: "error", message });
    }
  }

  return (
    <div className="w-full max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <Link href="/workflows" className="text-sm underline underline-offset-2">
          ← Workflows
        </Link>
        <span className="font-mono text-xs text-black/40 dark:text-white/40">
          {workflow.id.slice(0, 8)}
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto]">
        <input
          aria-label="Workflow title"
          value={title}
          onChange={(e) => {
            setTitle(e.target.value);
            setSave({ kind: "idle" });
          }}
          className="rounded border border-black/15 bg-transparent px-3 py-2 text-lg font-semibold dark:border-white/15"
        />
        <select
          aria-label="Status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded border border-black/15 bg-transparent px-2 py-2 text-sm dark:border-white/15"
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <input
          aria-label="Schedule (cron)"
          value={cron}
          onChange={(e) => setCron(e.target.value)}
          placeholder="cron e.g. 0 9 * * *"
          className="rounded border border-black/15 bg-transparent px-2 py-2 font-mono text-xs dark:border-white/15"
        />
      </div>

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
        <SortableContext items={steps.map((s) => s.key)} strategy={verticalListSortingStrategy}>
          <ol className="space-y-3">
            {steps.map((step, i) => (
              <StepNode
                key={step.key}
                step={step}
                index={i}
                total={steps.length}
                onChange={(patch) => patchStep(step.key, patch)}
                onRemove={() => {
                  setSteps((prev) => prev.filter((s) => s.key !== step.key));
                  setSave({ kind: "idle" });
                }}
                onMove={(to) => setSteps(move(steps, i, to))}
              />
            ))}
          </ol>
        </SortableContext>
      </DndContext>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => {
            setSteps((prev) => [...prev, blankStep()]);
            setSave({ kind: "idle" });
          }}
          className="rounded-lg border border-black/15 px-3 py-2 text-sm hover:bg-black/[0.03] dark:border-white/15 dark:hover:bg-white/[0.05]"
        >
          + Add step
        </button>
        <button
          type="button"
          onClick={onSave}
          disabled={save.kind === "saving" || steps.length === 0}
          className="rounded-lg bg-foreground px-4 py-2 text-sm font-medium text-background hover:opacity-90 disabled:opacity-40"
        >
          {save.kind === "saving" ? "Saving…" : "Save changes"}
        </button>
        {save.kind === "saved" && (
          <span className="text-sm text-green-600 dark:text-green-300">Saved ✓</span>
        )}
        {save.kind === "error" && (
          <span className="text-sm text-red-600 dark:text-red-300">{save.message}</span>
        )}
      </div>
    </div>
  );
}
