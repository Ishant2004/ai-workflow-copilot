"use client";

import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import type { StepType } from "@/lib/api";
import { STEP_TYPE_META, STEP_TYPES } from "@/lib/constants";
import type { EditableStep } from "@/lib/steps";

interface Props {
  step: EditableStep;
  index: number;
  total: number;
  onChange: (patch: Partial<EditableStep>) => void;
  onRemove: () => void;
  onMove: (to: number) => void;
}

export function StepNode({ step, index, total, onChange, onRemove, onMove }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: step.key });
  const meta = STEP_TYPE_META[step.type];

  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`rounded-lg border border-black/10 bg-black/[0.02] p-4 dark:border-white/10 dark:bg-white/[0.03] ${
        isDragging ? "opacity-60" : ""
      }`}
    >
      <div className="flex items-start gap-3">
        <button
          type="button"
          className="mt-1 cursor-grab touch-none rounded px-1 text-black/40 hover:text-black/70 dark:text-white/40 dark:hover:text-white/70"
          aria-label={`Drag step ${index + 1}`}
          {...attributes}
          {...listeners}
        >
          ⠿
        </button>
        <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-black/10 text-xs font-medium dark:bg-white/10">
          {index + 1}
        </span>

        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label="Step type"
              value={step.type}
              onChange={(e) => onChange({ type: e.target.value as StepType })}
              className="rounded border border-black/15 bg-transparent px-2 py-1 text-sm dark:border-white/15"
            >
              {STEP_TYPES.map((t) => (
                <option key={t} value={t}>
                  {STEP_TYPE_META[t].label}
                </option>
              ))}
            </select>
            <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${meta.badge}`}>
              {meta.label}
            </span>
          </div>

          <input
            aria-label="Step name"
            value={step.name}
            onChange={(e) => onChange({ name: e.target.value })}
            placeholder="Step name"
            className="w-full rounded border border-black/15 bg-transparent px-2 py-1 text-sm dark:border-white/15"
          />
          <input
            aria-label="Step description"
            value={step.description}
            onChange={(e) => onChange({ description: e.target.value })}
            placeholder="Description (optional)"
            className="w-full rounded border border-black/15 bg-transparent px-2 py-1 text-sm dark:border-white/15"
          />
          <textarea
            aria-label="Step config (JSON)"
            value={step.configText}
            onChange={(e) => onChange({ configText: e.target.value })}
            rows={2}
            spellCheck={false}
            className="w-full resize-y rounded border border-black/15 bg-transparent px-2 py-1 font-mono text-xs dark:border-white/15"
          />
        </div>

        <div className="flex shrink-0 flex-col gap-1 text-xs">
          <button
            type="button"
            onClick={() => onMove(index - 1)}
            disabled={index === 0}
            aria-label="Move up"
            className="rounded px-1.5 py-0.5 hover:bg-black/5 disabled:opacity-30 dark:hover:bg-white/10"
          >
            ↑
          </button>
          <button
            type="button"
            onClick={() => onMove(index + 1)}
            disabled={index === total - 1}
            aria-label="Move down"
            className="rounded px-1.5 py-0.5 hover:bg-black/5 disabled:opacity-30 dark:hover:bg-white/10"
          >
            ↓
          </button>
          <button
            type="button"
            onClick={onRemove}
            aria-label="Remove step"
            className="rounded px-1.5 py-0.5 text-red-600 hover:bg-red-500/10 dark:text-red-300"
          >
            ✕
          </button>
        </div>
      </div>
    </li>
  );
}
