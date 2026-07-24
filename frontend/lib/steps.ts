/**
 * Pure helpers for the step editor: the drag-reorder move, and conversion between
 * the API's steps and the editor's local model. Keeping these pure makes the
 * editor's core logic testable without simulating drag events.
 */
import type { StepInput, StepType, WorkflowStep } from "./api";

/** Editor-local step model. `key` is a stable client id for React/DnD. */
export interface EditableStep {
  key: string;
  type: StepType;
  name: string;
  description: string;
  configText: string; // JSON text, edited as-is and parsed on save
}

export class ConfigParseError extends Error {}

function newKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2);
}

export function blankStep(type: StepType = "web_search"): EditableStep {
  return { key: newKey(), type, name: "", description: "", configText: "{}" };
}

export function fromWorkflowStep(step: WorkflowStep): EditableStep {
  return {
    key: step.id,
    type: step.type,
    name: step.name,
    description: step.description ?? "",
    configText: JSON.stringify(step.config ?? {}, null, 2),
  };
}

/** Move the item at `from` to index `to`, returning a new array (out-of-range = no-op). */
export function move<T>(items: readonly T[], from: number, to: number): T[] {
  if (from < 0 || from >= items.length || to < 0 || to >= items.length || from === to) {
    return [...items];
  }
  const next = [...items];
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  return next;
}

/** Convert an editable step to the API shape, validating name + config JSON. */
export function toStepInput(step: EditableStep): StepInput {
  const name = step.name.trim();
  if (!name) {
    throw new ConfigParseError(`Step "${step.type}" needs a name.`);
  }
  let config: Record<string, unknown>;
  try {
    config = step.configText.trim() ? JSON.parse(step.configText) : {};
  } catch {
    throw new ConfigParseError(`Step "${name}" has invalid JSON config.`);
  }
  if (typeof config !== "object" || Array.isArray(config) || config === null) {
    throw new ConfigParseError(`Step "${name}" config must be a JSON object.`);
  }
  return {
    type: step.type,
    name,
    description: step.description.trim() || null,
    config,
  };
}
