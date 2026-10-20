import assert from "node:assert/strict";
import test from "node:test";

import { resolveVisualSpec, type ExplainerScene } from "./Explainer";

const makeScene = (
  narration: string,
  visualDescription = "",
  visual?: ExplainerScene["visual"],
): ExplainerScene => ({
  sceneNumber: 1,
  narration,
  visualDescription,
  audioFile: "audio/scene_001.mp3",
  durationInFrames: 120,
  from: 0,
  ...(visual ? { visual } : {}),
});

test("physics fallback selects a Newton's second law diagram", () => {
  const spec = resolveVisualSpec(
    makeScene(
      "Newton's second law relates net force, mass, and acceleration.",
    ),
    "Physics fundamentals",
    "physics",
  );

  assert.equal(spec.type, "flow");
  assert.equal(spec.title, "Newton's Second Law");

  if (spec.type !== "flow") {
    assert.fail("Expected a flow visual.");
  }

  assert.deepEqual(
    spec.nodes.map((node) => node.label),
    ["NET FORCE", "MASS", "ACCELERATION"],
  );
});

test("physics fallback selects a potential-energy diagram", () => {
  const spec = resolveVisualSpec(
    makeScene(
      "Gravitational potential energy increases with mass and height.",
    ),
    "Physics fundamentals",
    "physics",
  );

  assert.equal(spec.type, "flow");
  assert.equal(spec.title, "Gravitational Potential Energy");
});

test("CS fallback selects an algorithm diagram", () => {
  const spec = resolveVisualSpec(
    makeScene("An algorithm searches data and returns a result."),
    "Computer science fundamentals",
    "cs",
  );

  assert.equal(spec.type, "flow");
  assert.equal(spec.title, "Algorithm Execution");

  if (spec.type !== "flow") {
    assert.fail("Expected a flow visual.");
  }

  assert.deepEqual(
    spec.nodes.map((node) => node.label),
    ["DATA", "ALGORITHM", "RESULT"],
  );
});

test("valid planned visuals take priority over category fallbacks", () => {
  const planned = {
    type: "flow" as const,
    title: "Planner-selected visual",
    nodes: [
      { label: "SOURCE", icon: "dot" as const, color: "teal" as const },
      { label: "RESULT", icon: "check" as const, color: "gold" as const },
    ],
  };

  const spec = resolveVisualSpec(
    makeScene(
      "Newton's second law relates force, mass, and acceleration.",
      "",
      planned,
    ),
    "Physics fundamentals",
    "physics",
  );

  assert.equal(spec.title, "Planner-selected visual");
});

test("valid planned array visuals take priority over category fallbacks", () => {
  const planned = {
    type: "array" as const,
    title: "Binary search",
    values: [3, 8, 12, 19, 25, 31, 42],
    algorithm: "binary-search" as const,
    target: 25,
  };

  const spec = resolveVisualSpec(
    makeScene(
      "Binary search repeatedly checks the middle value and narrows the search range.",
      "",
      planned,
    ),
    "Computer science fundamentals",
    "cs",
  );

  assert.equal(spec.type, "array");
  assert.equal(spec.title, "Binary search");

  if (spec.type !== "array") {
    assert.fail("Expected the planned array visual.");
  }

  assert.deepEqual(spec.values, [3, 8, 12, 19, 25, 31, 42]);
  assert.equal(spec.algorithm, "binary-search");
  assert.equal(spec.target, 25);
});

test("binary-search introduction uses an array overview fallback", () => {
  const spec = resolveVisualSpec(
    makeScene("Imagine searching a sorted list for one target value."),
    "How binary search works",
    "cs",
  );

  assert.equal(spec.type, "array");
  if (spec.type !== "array") assert.fail("Expected an array visual.");

  assert.equal(spec.algorithm, "binary-search");
  assert.equal(spec.phase, "overview");
  assert.equal(spec.target, 25);
});

test("binary-search elimination narration selects the elimination phase", () => {
  const spec = resolveVisualSpec(
    makeScene(
      "The half in which the target cannot lie is eliminated, and the search continues on the remaining half.",
    ),
    "How binary search works",
    "cs",
  );

  assert.equal(spec.type, "array");
  if (spec.type !== "array") assert.fail("Expected an array visual.");

  assert.equal(spec.algorithm, "binary-search");
  assert.equal(spec.phase, "elimination");
});

test("binary-search failure narration selects an absent target", () => {
  const spec = resolveVisualSpec(
    makeScene("If the search ends with the remaining half being empty, the target is not in the array."),
    "How binary search works",
    "cs",
  );

  assert.equal(spec.type, "array");
  if (spec.type !== "array") assert.fail("Expected an array visual.");

  assert.equal(spec.algorithm, "binary-search");
  assert.equal(spec.phase, "not-found");
  assert.equal(spec.target, 26);
});
