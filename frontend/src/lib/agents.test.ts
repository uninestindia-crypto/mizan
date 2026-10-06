import { describe, expect, it } from "vitest";
import {
  type Agent,
  type AgentInput,
  addStep,
  appPath,
  blankForm,
  copyTarget,
  editTarget,
  formFromAgent,
  groupProblems,
  isDirty,
  LIMITS,
  moveStep,
  newTarget,
  normalizeSymbol,
  type Problem,
  problemsFromError,
  type Proposal,
  proposalAction,
  removeStep,
  setStep,
  stepHasProblem,
  symbolProblem,
  toggleTool,
  toInput,
  toolLabels,
  usesSymbol,
  validateForm,
} from "./agents";
import { ApiError } from "./api";

const agent = (over: Partial<Agent> = {}): Agent => ({
  id: "a1",
  name: "My check",
  description: "",
  instructions: "",
  tools: ["stock_facts"],
  steps: ["Show the facts about {symbol}."],
  needs_symbol: true,
  built_in: false,
  ...over,
});

const filled = (over: Partial<AgentInput> = {}): AgentInput => ({
  name: "My check",
  description: "",
  instructions: "",
  tools: ["stock_facts"],
  steps: ["Show the facts about {symbol}."],
  ...over,
});

const messagesOf = (problems: Problem[]) => problems.map((p) => p.message);

describe("ordering the steps", () => {
  const steps = ["a", "b", "c"];

  it("moves a step up or down by swapping it with its neighbour", () => {
    expect(moveStep(steps, 1, -1)).toEqual(["b", "a", "c"]);
    expect(moveStep(steps, 1, 1)).toEqual(["a", "c", "b"]);
  });

  it("leaves the list alone at either end and for a step that does not exist", () => {
    expect(moveStep(steps, 0, -1)).toEqual(steps);
    expect(moveStep(steps, 2, 1)).toEqual(steps);
    expect(moveStep(steps, 7, -1)).toEqual(steps);
    expect(moveStep(steps, -1, 1)).toEqual(steps);
  });

  it("never changes the list it was given", () => {
    const original = ["a", "b"];
    moveStep(original, 0, 1);
    removeStep(original, 0);
    setStep(original, 0, "z");
    addStep(original);
    expect(original).toEqual(["a", "b"]);
  });

  it("adds, removes and rewrites a step", () => {
    expect(addStep(["a"])).toEqual(["a", ""]);
    expect(removeStep(steps, 1)).toEqual(["a", "c"]);
    expect(setStep(steps, 2, "z")).toEqual(["a", "b", "z"]);
  });

  it("stops adding at the most steps an agent may have", () => {
    const full = Array.from({ length: LIMITS.steps }, (_, i) => `s${i}`);
    expect(addStep(full)).toBe(full);
  });
});

describe("filling the form", () => {
  it("starts empty with one blank step", () => {
    expect(blankForm()).toEqual({ name: "", description: "", instructions: "", tools: [], steps: [""] });
  });

  it("gives a copy a new name, so saving it never replaces the original", () => {
    const form = formFromAgent(agent({ name: "Check a stock", built_in: true }), true);
    expect(form.name).toBe("My copy of Check a stock");
    expect(formFromAgent(agent({ name: "Check a stock" }), false).name).toBe("Check a stock");
  });

  it("keeps a copy's name within the length the engine accepts", () => {
    expect(formFromAgent(agent({ name: "x".repeat(60) }), true).name.length).toBeLessThanOrEqual(LIMITS.name);
  });

  it("does not share its lists with the agent it was made from", () => {
    const source = agent();
    const form = formFromAgent(source, false);
    form.steps.push("more");
    form.tools.push("other");
    expect(source.steps).toHaveLength(1);
    expect(source.tools).toHaveLength(1);
  });

  it("builds the three targets the screen opens", () => {
    expect(newTarget()).toMatchObject({ id: null, heading: "New agent" });
    expect(editTarget(agent())).toMatchObject({ id: "a1", heading: "Edit My check" });
    const copy = copyTarget(agent({ id: "recipe", built_in: true }));
    expect(copy).toMatchObject({ id: null, heading: "Your copy of My check" });
  });

  it("sends the text trimmed", () => {
    const sent = toInput(filled({ name: "  My check ", steps: [" one ", "two  "], instructions: "  short " }));
    expect(sent).toMatchObject({ name: "My check", instructions: "short", steps: ["one", "two"] });
  });
});

describe("noticing unsaved changes", () => {
  const initial = filled({ tools: ["a", "b"] });

  it("is clean until something changes", () => {
    expect(isDirty(filled({ tools: ["a", "b"] }), initial)).toBe(false);
  });

  it("does not mind the order the boxes were ticked in", () => {
    expect(isDirty(filled({ tools: ["b", "a"] }), initial)).toBe(false);
  });

  it("notices a change in any field", () => {
    expect(isDirty({ ...initial, name: "Other" }, initial)).toBe(true);
    expect(isDirty({ ...initial, description: "x" }, initial)).toBe(true);
    expect(isDirty({ ...initial, instructions: "x" }, initial)).toBe(true);
    expect(isDirty({ ...initial, tools: ["a"] }, initial)).toBe(true);
    expect(isDirty({ ...initial, steps: ["a", "b"] }, initial)).toBe(true);
  });

  it("ticks and unticks a box", () => {
    expect(toggleTool(["a"], "b")).toEqual(["a", "b"]);
    expect(toggleTool(["a", "b"], "a")).toEqual(["b"]);
  });
});

describe("checking the form before it is sent", () => {
  it("accepts a complete form", () => {
    expect(validateForm(filled())).toEqual([]);
  });

  it("asks for a name, a step and something to look at, in the engine's own words", () => {
    const found = validateForm({ name: " ", description: "", instructions: "", tools: [], steps: [] });
    expect(found).toEqual([
      { field: "name", message: "Give your agent a name." },
      { field: "steps", message: "Add at least one step, for example: Check {symbol} against the halal screener." },
      { field: "tools", message: "Tick at least one thing this agent may look at." },
    ]);
  });

  it("points at an empty step by its number", () => {
    const found = validateForm(filled({ steps: ["Fine", "  "] }));
    expect(found).toEqual([{ field: "steps", message: "Step 2 is empty. Write what to do, or remove the step." }]);
  });

  it("allows only {symbol} as a fill-in", () => {
    const found = validateForm(filled({ steps: ["Look at {symbol}", "Look at {price}"] }));
    expect(messagesOf(found)).toEqual(["Step 2 uses {price}. The only fill-in you can use is {symbol}."]);
  });

  it("keeps to the engine's limits", () => {
    const found = validateForm(
      filled({
        name: "n".repeat(LIMITS.name + 1),
        description: "d".repeat(LIMITS.description + 1),
        instructions: "i".repeat(LIMITS.instructions + 1),
        steps: ["s".repeat(LIMITS.step + 1)],
      }),
    );
    expect(found.map((p) => p.field)).toEqual(["name", "description", "instructions", "steps"]);
    expect(messagesOf(found)[0]).toBe("Make the name shorter (up to 60 letters).");
  });

  it("allows no more than the most steps", () => {
    const found = validateForm(filled({ steps: Array.from({ length: LIMITS.steps + 1 }, () => "Step") }));
    expect(messagesOf(found)).toEqual([`Use at most ${LIMITS.steps} steps.`]);
  });

  it("knows when a step uses the stock's name", () => {
    expect(usesSymbol(filled())).toBe(true);
    expect(usesSymbol(filled({ steps: ["Say hello"], instructions: "About {symbol}" }))).toBe(true);
    expect(usesSymbol(filled({ steps: ["Say hello"] }))).toBe(false);
  });
});

describe("showing the engine's problems under the right field", () => {
  const rejected = (problems: unknown, status = 422) =>
    new ApiError("AGENT_INVALID", "Check the highlighted fields.", status, { problems });

  it("reads the list of problems from a rejected form, exactly as written", () => {
    const list = [{ field: "name", message: "Give your agent a name." }];
    expect(problemsFromError(rejected(list))).toEqual(list);
  });

  it("ignores anything that is not a problem, and any other kind of error", () => {
    expect(problemsFromError(rejected([{ field: 1, message: "x" }, null, "text"]))).toBeNull();
    expect(problemsFromError(rejected("nope"))).toBeNull();
    expect(problemsFromError(rejected([{ field: "name", message: "x" }], 500))).toBeNull();
    expect(problemsFromError(new ApiError("VALIDATION_ERROR", "bad", 422, { errors: [] }))).toBeNull();
    expect(problemsFromError(new Error("boom"))).toBeNull();
    expect(problemsFromError(null)).toBeNull();
  });

  it("groups messages by field and puts an unknown field in a place of its own", () => {
    const grouped = groupProblems([
      { field: "name", message: "A" },
      { field: "steps", message: "B" },
      { field: "steps", message: "C" },
      { field: "mystery", message: "D" },
    ]);
    expect(grouped.name).toEqual(["A"]);
    expect(grouped.steps).toEqual(["B", "C"]);
    expect(grouped.other).toEqual(["D"]);
    expect(grouped.tools).toEqual([]);
  });

  it("finds which step a message is about", () => {
    const messages = ["Step 2 is empty. Write what to do, or remove the step.", "Use at most 8 steps."];
    expect(stepHasProblem(messages, 2)).toBe(true);
    expect(stepHasProblem(messages, 1)).toBe(false);
    expect(stepHasProblem(messages, 8)).toBe(false);
  });
});

describe("what an agent may look at", () => {
  const tools = [{ name: "stock_facts", label: "Price facts", help: "Shows price facts.", description: "d" }];

  it("shows the plain label and never the name it is saved under", () => {
    expect(toolLabels(["stock_facts"], tools)).toEqual(["Price facts"]);
    expect(toolLabels(["stock_facts", "unknown_tool"], tools)).toEqual(["Price facts"]);
    expect(toolLabels(["stock_facts"], undefined)).toEqual([]);
  });
});

describe("the stock an agent is run for", () => {
  it("writes it in upper case with no spaces", () => {
    expect(normalizeSymbol(" tc s ")).toBe("TCS");
    expect(normalizeSymbol("m&m")).toBe("M&M");
  });

  it("accepts NSE symbols, including the ones with & or -", () => {
    for (const ok of ["TCS", "m&m", "BAJAJ-AUTO", "-TCS", "20MICRONS", "x".repeat(15)]) {
      expect(symbolProblem(ok)).toBeNull();
    }
  });

  it("asks for a symbol, and refuses anything else, in plain words", () => {
    expect(symbolProblem("")).toBe("Type the stock's NSE symbol, for example TCS.");
    expect(symbolProblem("   ")).toBe("Type the stock's NSE symbol, for example TCS.");
    for (const bad of ["TCS!", "<b>", "a/b", "A_B", "x".repeat(16), "x".repeat(40)]) {
      expect(symbolProblem(bad)).toBe("Use letters and numbers only, for example TCS or M&M.");
    }
  });
});

describe("the buttons under a result", () => {
  const navigate = (path: string | null): Proposal => ({ kind: "navigate", label: "Open", path, symbol: null });

  it("opens a screen inside the app", () => {
    expect(proposalAction(navigate("/stock/TCS"))).toEqual({ type: "navigate", path: "/stock/TCS" });
    expect(appPath("/settings/accounts")).toBe("/settings/accounts");
  });

  it("never follows a web address, a script or a path that leaves the app", () => {
    const unsafe = ["https://evil.example", "//evil.example", "javascript:alert(1)", "/\\evil"];
    unsafe.push("stock", "", null as never, "/a b");
    for (const bad of unsafe) {
      expect(appPath(bad)).toBeNull();
      expect(proposalAction(navigate(bad))).toBeNull();
    }
  });

  it("asks for a second opinion only for a real stock", () => {
    const opinion = (symbol: string | null): Proposal => ({ kind: "second_opinion", label: "Ask", path: null, symbol });
    expect(proposalAction(opinion("tcs"))).toEqual({ type: "second_opinion", symbol: "TCS" });
    expect(proposalAction(opinion(null))).toBeNull();
    expect(proposalAction(opinion("<img>"))).toBeNull();
  });
});
