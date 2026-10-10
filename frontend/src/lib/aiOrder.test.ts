import { describe, expect, it } from "vitest";
import {
  added,
  anyLevels,
  appOptions,
  candidates,
  choose,
  effectiveOrder,
  keyOptions,
  levelsFor,
  type ModelOption,
  move,
  orderView,
  savedChoice,
  selectionOf,
  without,
  withKept,
} from "./aiOrder";
import { type AiApp, type AiChoice, type AiStatus, buildPlan, type OrderEntry, unconfirmed } from "./aiSource";
import type { AiModels, CliCapabilities } from "./types";

const app = (id: string, state: AiApp["state"]): AiApp => ({
  id,
  name: id === "claude" ? "Claude Code" : id.charAt(0).toUpperCase() + id.slice(1),
  label: `${id} (sign-in)`,
  state,
  installed: state !== "NOT_INSTALLED",
  ready: state === "CONNECTED",
});
const keys = (...saved: string[]) =>
  ["anthropic", "openai", "gemini", "groq"].map((id) => ({ id, label: id.toUpperCase(), ready: saved.includes(id) }));
const AUTO: AiChoice = { source: "cli", cli: null, api: null, fallback: true };
const STATUS: AiStatus = {
  ai_ready: true,
  apps: [app("claude", "CONNECTED"), app("codex", "NEEDS_SIGN_IN"), app("antigravity", "NOT_INSTALLED")],
  ai: AUTO,
  providers: keys("openai"),
};
const entry = (id: string, model: string | null = null, thinking: string | null = null): OrderEntry => ({ id, model, thinking });
const ids = (list: readonly OrderEntry[]) => list.map((e) => e.id);

describe("what can be on the list", () => {
  it("names every app and provider with where it stands", () => {
    const found = candidates(STATUS);
    expect(found.map((c) => [c.id, c.state])).toEqual([
      ["cli:claude", "ready"],
      ["cli:codex", "signed_out"],
      ["cli:antigravity", "missing"],
      ["anthropic", "missing"],
      ["openai", "ready"],
      ["gemini", "missing"],
      ["groq", "missing"],
    ]);
    expect(found[0]?.setupName).toBe("Claude Code");
  });
});

describe("the order in force", () => {
  it("is the built-in order, apps first then keys, until the person saves their own", () => {
    expect(ids(effectiveOrder(STATUS, AUTO))).toEqual(["cli:claude", "cli:codex", "openai"]);
  });

  it("puts a key first when the person had chosen keys first", () => {
    expect(ids(effectiveOrder(STATUS, { ...AUTO, source: "api" }))).toEqual(["openai", "cli:claude", "cli:codex"]);
  });

  it("is the person's own order once saved", () => {
    const order = [entry("openai"), entry("cli:claude", "fable", "high")];
    expect(effectiveOrder(STATUS, { ...AUTO, order })).toEqual(order);
  });
});

describe("the view of the list", () => {
  it("lists what is set up, offers what is left, and keeps what is missing apart", () => {
    const view = orderView(STATUS, AUTO);
    expect(view.listed.map((l) => l.candidate.id)).toEqual(["cli:claude", "cli:codex", "openai"]);
    expect(view.addable).toEqual([]);
    expect(view.missing.map((c) => c.id)).toEqual(["cli:antigravity", "anthropic", "gemini", "groq"]);
  });

  it("offers an AI that was taken off the list, and ignores one saved that is no longer set up", () => {
    const order = [entry("cli:claude"), entry("anthropic", "x")];
    const view = orderView(STATUS, { ...AUTO, order });
    expect(view.listed.map((l) => l.candidate.id)).toEqual(["cli:claude"]);
    expect(view.addable.map((c) => c.id)).toEqual(["cli:codex", "openai"]);
    expect(view.missing.map((c) => c.id)).toContain("anthropic");
  });

  it("lists an AI once even if the saved order names it twice", () => {
    const view = orderView(STATUS, { ...AUTO, order: [entry("openai", "a"), entry("openai", "b")] });
    expect(view.listed).toHaveLength(1);
    expect(view.listed[0]?.entry.model).toBe("a");
  });

  it("agrees with the plan the sentence at the top is built from", () => {
    const order = [entry("openai"), entry("cli:claude"), entry("cli:codex")];
    const choice = { ...AUTO, order };
    expect(buildPlan(STATUS, choice).map((p) => p.id)).toEqual(orderView(STATUS, choice).listed.map((l) => l.candidate.id.replace("cli:", "")));
  });

  it("asks only the first with the backup off", () => {
    const choice = { ...AUTO, fallback: false, order: [entry("openai"), entry("cli:claude")] };
    expect(buildPlan(STATUS, choice).map((p) => p.id)).toEqual(["openai"]);
  });
});

describe("editing the list", () => {
  const list = [entry("a"), entry("b"), entry("c")];

  it("moves one place at a time and stops at the ends", () => {
    expect(ids(move(list, 1, -1))).toEqual(["b", "a", "c"]);
    expect(ids(move(list, 1, 1))).toEqual(["a", "c", "b"]);
    expect(ids(move(list, 0, -1))).toEqual(["a", "b", "c"]);
    expect(ids(move(list, 2, 1))).toEqual(["a", "b", "c"]);
  });

  it("sets the model and level of one AI only", () => {
    expect(choose(list, "b", "m", "high")).toEqual([entry("a"), entry("b", "m", "high"), entry("c")]);
  });

  it("takes one off and puts one on once", () => {
    expect(ids(without(list, "b"))).toEqual(["a", "c"]);
    expect(ids(added(list, "d"))).toEqual(["a", "b", "c", "d"]);
    expect(ids(added(list, "a"))).toEqual(["a", "b", "c"]);
  });

  it("keeps what was chosen for an AI that is not set up right now when saving", () => {
    const choice = { ...AUTO, order: [entry("cli:claude"), entry("anthropic", "claude-x", "max")] };
    const saved = withKept([entry("cli:claude"), entry("openai")], STATUS, choice);
    expect(saved).toEqual([entry("cli:claude"), entry("openai"), entry("anthropic", "claude-x", "max")]);
    expect(withKept([entry("openai")], STATUS, AUTO)).toEqual([entry("openai")]);
  });
});

describe("models and thinking levels", () => {
  const plain: ModelOption = { value: "gpt-6", name: "GPT-6", levels: ["low", "high"], variants: null, newest: true };
  const tiered: ModelOption = {
    value: "flash",
    name: "Flash",
    levels: ["low", "medium", "high"],
    variants: { low: "flash-low", medium: "flash-medium", high: "flash-high" },
    newest: false,
  };
  const noMedium: ModelOption = { ...tiered, value: "pro", variants: { low: "pro-low", high: "pro-high" }, levels: ["low", "high"] };

  it("saves the model and the level as they are for an ordinary model", () => {
    expect(savedChoice(plain, "high")).toEqual({ model: "gpt-6", thinking: "high" });
    expect(savedChoice(plain, null)).toEqual({ model: "gpt-6", thinking: null });
    expect(savedChoice(null, "max")).toEqual({ model: null, thinking: "max" });
  });

  it("saves the level inside the name where the app works that way, and defaults to the middle tier", () => {
    expect(savedChoice(tiered, "high")).toEqual({ model: "flash-high", thinking: null });
    expect(savedChoice(tiered, null)).toEqual({ model: "flash-medium", thinking: null });
    expect(savedChoice(tiered, "max")).toEqual({ model: "flash-medium", thinking: null });
    expect(savedChoice(noMedium, null)).toEqual({ model: "pro-low", thinking: null });
  });

  it("reads a saved choice back, including a level that lives in the name", () => {
    const options = [plain, tiered];
    expect(selectionOf(options, entry("x", "gpt-6", "low"))).toEqual({ option: plain, level: "low", unlisted: null });
    expect(selectionOf(options, entry("x", "flash-high"))).toEqual({ option: tiered, level: "high", unlisted: null });
    expect(selectionOf(options, entry("x", null, "max"))).toEqual({ option: null, level: "max", unlisted: null });
    expect(selectionOf(options, entry("x", "gone", "low"))).toEqual({ option: null, level: "low", unlisted: "gone" });
  });

  it("offers a model's own levels, or all of the AI's when no model is picked", () => {
    expect(levelsFor({ option: plain, level: null, unlisted: null }, ["low", "high", "max"])).toEqual(["low", "high"]);
    expect(levelsFor({ option: null, level: null, unlisted: null }, ["low", "high", "max"])).toEqual(["low", "high", "max"]);
  });

  it("builds the options from what an app reports", () => {
    const caps = {
      thinking_levels: ["low", "high"],
      models: [
        { id: "m", name: "M", description: "", context_window: null, released: null, newest: true, recommended: false, thinking: { levels: ["low"], default: null }, variants: null },
        { id: "n", name: "N", description: "", context_window: null, released: null, newest: false, recommended: false, thinking: null, variants: null },
      ],
    } as unknown as CliCapabilities;
    expect(appOptions(caps).map((o) => [o.value, o.levels, o.newest])).toEqual([
      ["m", ["low"], true],
      ["n", [], false],
    ]);
    expect(anyLevels(caps, null)).toEqual(["low", "high"]);
    expect(appOptions(undefined)).toEqual([]);
  });

  it("builds the options for a provider, using what it reports and otherwise the levels such a provider takes", () => {
    const found: AiModels = {
      provider: "anthropic",
      total: 2,
      newest: [
        { id: "c1", name: "C1", created: 1, effort_levels: ["low", "max"] },
        { id: "c2", name: "C2", created: 2 },
      ],
    };
    expect(keyOptions("anthropic", found).map((o) => o.levels)).toEqual([["low", "max"], []]);
    const openai: AiModels = { provider: "openai", total: 1, newest: [{ id: "g", name: "g", created: null }] };
    expect(keyOptions("openai", openai)[0]?.levels).toEqual(["low", "medium", "high", "xhigh"]);
    expect(anyLevels(undefined, "groq")).toEqual(["low", "medium", "high"]);
    expect(anyLevels(undefined, "deepseek")).toEqual([]);
  });
});

describe("a change carried until the engine shows it", () => {
  const status = (ai: Partial<AiChoice>, defaults?: AiStatus["defaults"]) => ({ ai: { ...AUTO, ...ai }, defaults });

  it("is kept while the engine still shows the old value, and dropped once it agrees", () => {
    const wanted = { ai_order: [entry("openai")], ai_fallback: false };
    expect(unconfirmed(wanted, status({ order: [] }))).toEqual({ ai_order: [entry("openai")], ai_fallback: false });
    expect(unconfirmed(wanted, status({ order: [entry("openai")] }))).toEqual({ ai_fallback: false });
    expect(unconfirmed(wanted, status({ order: [entry("openai")], fallback: false }))).toEqual({});
  });

  it("treats a missing list as an empty one and compares the speed by what was changed", () => {
    expect(unconfirmed({ ai_order: [] }, status({}))).toEqual({});
    const speed = { ai_defaults: { speed: "careful" as const } };
    expect(unconfirmed(speed, status({}, { speed: "balanced", helpers: 1 }))).toEqual(speed);
    expect(unconfirmed(speed, status({}, { speed: "careful", helpers: 1 }))).toEqual({});
  });

  it("returns the very same object when nothing is confirmed, so a screen does not redraw for nothing", () => {
    const wanted = { ai_cli: "codex" };
    expect(unconfirmed(wanted, status({ cli: null }))).toBe(wanted);
  });
});
