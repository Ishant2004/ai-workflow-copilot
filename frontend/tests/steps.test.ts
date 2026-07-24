import { describe, expect, it } from "vitest";

import type { WorkflowStep } from "@/lib/api";
import { ConfigParseError, fromWorkflowStep, move, toStepInput } from "@/lib/steps";

describe("move", () => {
  it("reorders items and returns a new array", () => {
    const r = move(["a", "b", "c"], 0, 2);
    expect(r).toEqual(["b", "c", "a"]);
  });

  it("is a no-op for out-of-range or equal indices", () => {
    expect(move(["a", "b"], 0, 0)).toEqual(["a", "b"]);
    expect(move(["a", "b"], -1, 1)).toEqual(["a", "b"]);
    expect(move(["a", "b"], 0, 9)).toEqual(["a", "b"]);
  });
});

describe("fromWorkflowStep", () => {
  it("maps an API step into the editable model with JSON config text", () => {
    const step: WorkflowStep = {
      id: "s1",
      order_index: 0,
      type: "web_search",
      name: "Search",
      description: "find",
      config: { query: "ai" },
    };
    const e = fromWorkflowStep(step);
    expect(e.key).toBe("s1");
    expect(e.name).toBe("Search");
    expect(JSON.parse(e.configText)).toEqual({ query: "ai" });
  });
});

describe("toStepInput", () => {
  const base = { key: "k", type: "web_search" as const, description: "", configText: "{}" };

  it("parses a valid step", () => {
    const out = toStepInput({ ...base, name: "  Search  ", configText: '{"query":"x"}' });
    expect(out).toEqual({
      type: "web_search",
      name: "Search",
      description: null,
      config: { query: "x" },
    });
  });

  it("rejects a blank name", () => {
    expect(() => toStepInput({ ...base, name: "  " })).toThrow(ConfigParseError);
  });

  it("rejects invalid JSON config", () => {
    expect(() => toStepInput({ ...base, name: "S", configText: "{bad" })).toThrow(
      ConfigParseError,
    );
  });

  it("rejects non-object config", () => {
    expect(() => toStepInput({ ...base, name: "S", configText: "[1,2]" })).toThrow(
      ConfigParseError,
    );
  });
});
