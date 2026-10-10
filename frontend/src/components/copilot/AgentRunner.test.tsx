import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AgentPoll } from "../../lib/agentRun";
import type { AiStatus } from "../../lib/aiSource";
import { afterSaving, isSavable, isUsual, NO_PREFS, prefsBody } from "../../lib/answerPrefs";
import { api } from "../../lib/api";
import { openDrawer, say, Shell } from "./chatTestKit";
import { renderApp, serveApi } from "./testHarness";
import { agentPolling } from "./useAgentRun";

vi.mock("../../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../lib/api")>();
  return { ...original, api: vi.fn() };
});

const RUNS = "/api/v2/copilot/agent/runs";
const STATUS = "/api/v2/copilot/status";
const SETTINGS = "/api/v2/settings";
const CAPABILITIES = "/api/v2/cli/claude/capabilities";
const saves: unknown[] = [];

const done: AgentPoll = {
  status: "done",
  events: [],
  next: 0,
  pending: [],
  result: { reply: "Done.", steps: [], proposals: [], mode: "ai", provider: "cli:claude", model: "claude-x", error: null },
  error: null,
};

function status(over: Partial<AiStatus> = {}): AiStatus {
  return {
    ai_ready: true,
    apps: [{ id: "claude", name: "Claude Code", label: "Claude Code", state: "CONNECTED", installed: true, ready: true }],
    ai: { source: "cli", cli: null, api: null, fallback: true },
    providers: [{ id: "openai", label: "OpenAI", ready: true }],
    defaults: { speed: "balanced", helpers: 1 },
    agent_apps: ["cli:claude"],
    ...over,
  };
}

function engine(shown: AiStatus = status()) {
  const starts: { prefs?: unknown }[] = [];
  saves.length = 0;
  serveApi((method, path, body) => {
    if (method === "PUT" && path === SETTINGS) {
      saves.push(body);
      const sent = body as { ai_order?: unknown; ai_defaults?: unknown };
      return { ai_order: sent.ai_order ?? [], ai_defaults: sent.ai_defaults };
    }
    if (method === "POST" && path === RUNS) {
      starts.push(body as { prefs?: unknown });
      return { run_id: "run1" };
    }
    if (method === "GET" && path.startsWith(`${RUNS}/run1`)) return done;
    if (method === "GET" && path === STATUS) return structuredClone(shown);
    if (method === "GET" && path === CAPABILITIES) {
      return { agent_id: "claude", version: "1", source: "app", models: [], thinking_levels: ["low", "high"], note: "" };
    }
    throw new Error(`Unexpected call: ${method} ${path}`);
  });
  return starts;
}

async function openedInAgentMode() {
  renderApp(<Shell />);
  openDrawer();
  await screen.findByRole("dialog");
  fireEvent.click(screen.getByRole("radio", { name: "Agent" }));
  fireEvent.click(screen.getByRole("button", { name: /Ways to answer/ }));
}

beforeEach(() => {
  vi.mocked(api).mockReset();
  window.localStorage.clear();
  agentPolling.intervalMs = 15;
});
afterEach(() => {
  cleanup();
  agentPolling.intervalMs = 1000;
});

describe("who does the work of a task", () => {
  it("offers the apps that can do a whole task, by the name a person knows, only in agent mode", async () => {
    engine();
    renderApp(<Shell />);
    openDrawer();
    await screen.findByRole("dialog");
    fireEvent.click(screen.getByRole("button", { name: /Ways to answer/ }));
    await screen.findByRole("combobox", { name: "Which AI" });
    expect(screen.queryByRole("combobox", { name: "Who does the work" })).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: "Agent" }));
    const who = await screen.findByRole("combobox", { name: "Who does the work" });
    expect(who).toHaveValue("");
    expect(within(who).getByRole("option", { name: "Claude Code" })).toBeInTheDocument();
  });

  it("offers nothing when no app can do a task, so the choice never leads to a failure", async () => {
    engine(status({ agent_apps: [] }));
    await openedInAgentMode();
    await screen.findByRole("combobox", { name: "Which AI" });
    expect(screen.queryByRole("combobox", { name: "Who does the work" })).toBeNull();
  });

  it("explains in plain words what an app is allowed to do, and swaps the choices for that app's own", async () => {
    engine();
    await openedInAgentMode();
    fireEvent.change(await screen.findByRole("combobox", { name: "Who does the work" }), { target: { value: "cli:claude" } });
    expect(await screen.findByText(/does the whole task itself/)).toHaveTextContent(/asks you before it changes anything/);
    expect(screen.queryByRole("combobox", { name: "Which AI" })).toBeNull(); // the app is the AI now
    expect(screen.queryByRole("combobox", { name: "Who works on the task" })).toBeNull(); // and it works alone
    expect(await screen.findByText("Model")).toBeInTheDocument();
  });

  it("sends the app with the task, with its own model choices, and marks the panel changed", async () => {
    const starts = engine();
    await openedInAgentMode();
    fireEvent.change(await screen.findByRole("combobox", { name: "Who does the work" }), { target: { value: "cli:claude" } });
    expect(screen.getByText("Changed")).toBeInTheDocument();
    await say("check TCS");
    await waitFor(() => expect(starts).toHaveLength(1));
    expect(starts[0]?.prefs).toEqual({ ai: "cli:claude", runner: "cli:claude" });
  });

  it("goes back to the Copilot with its usual AIs when asked", async () => {
    const starts = engine();
    await openedInAgentMode();
    const who = await screen.findByRole("combobox", { name: "Who does the work" });
    fireEvent.change(who, { target: { value: "cli:claude" } });
    fireEvent.change(who, { target: { value: "" } });
    expect(await screen.findByRole("combobox", { name: "Which AI" })).toBeInTheDocument();
    await say("check TCS");
    await waitFor(() => expect(starts).toHaveLength(1));
    expect(starts[0]?.prefs).toBeUndefined();
  });

  it("does not offer to keep an app doing a task as the usual, because it is chosen again for each task", async () => {
    engine();
    await openedInAgentMode();
    fireEvent.change(await screen.findByRole("combobox", { name: "Who does the work" }), { target: { value: "cli:claude" } });
    expect(screen.queryByRole("button", { name: "Make this my usual" })).toBeNull();
    expect(screen.getByRole("button", { name: "Back to my usual" })).toBeInTheDocument();
  });

  it("keeps only the speed when the person makes it their usual, and leaves the app for this task", async () => {
    const starts = engine();
    await openedInAgentMode();
    fireEvent.change(await screen.findByRole("combobox", { name: "Who does the work" }), { target: { value: "cli:claude" } });
    fireEvent.click(screen.getByRole("radio", { name: "Careful" }));
    fireEvent.click(await screen.findByRole("button", { name: "Make this my usual" }));
    await screen.findByText("Saved");
    expect(saves).toEqual([{ ai_defaults: { speed: "careful" } }]); // the order is untouched
    expect(screen.getByRole("combobox", { name: "Who does the work" })).toHaveValue("cli:claude");
    await say("check TCS");
    await waitFor(() => expect(starts).toHaveLength(1));
    expect(starts[0]?.prefs).toEqual({ ai: "cli:claude", runner: "cli:claude" });
  });
});

describe("the choices as sent", () => {
  it("count the app as a change, but not as something to keep", () => {
    const withApp = { ...NO_PREFS, runner: "cli:claude" };
    expect(isUsual(withApp)).toBe(false);
    expect(isSavable(withApp)).toBe(false);
    expect(isSavable({ ...withApp, speed: "quick" as const })).toBe(true);
    expect(prefsBody(withApp)).toEqual({ runner: "cli:claude" });
    expect(prefsBody(NO_PREFS)).toBeUndefined();
  });

  it("keep, after saving, only what belongs to the one task", () => {
    expect(afterSaving({ ...NO_PREFS, speed: "quick", helpers: 2 })).toEqual(NO_PREFS);
    const task = { ...NO_PREFS, ai: "cli:claude", model: "opus", thinking: "high", runner: "cli:claude", speed: "quick" as const };
    expect(afterSaving(task)).toEqual({ ...NO_PREFS, ai: "cli:claude", model: "opus", thinking: "high", runner: "cli:claude" });
    expect(isSavable({ ...task, speed: null })).toBe(false); // the model and level picked for the app are not kept either
  });
});
