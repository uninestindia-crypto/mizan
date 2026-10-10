import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AgentPoll } from "../../lib/agentRun";
import { api, ApiError } from "../../lib/api";
import { box, CHAT, openDrawer, say, Shell } from "./chatTestKit";
import { callsTo, renderApp, serveApi } from "./testHarness";
import { agentPolling } from "./useAgentRun";

vi.mock("../../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../lib/api")>();
  return { ...original, api: vi.fn() };
});

const RUNS = "/api/v2/copilot/agent/runs";
const STATUS = "/api/v2/copilot/status";

const event = (n: number, text: string, kind = "step", ok = true) => ({ n, kind, text, ok });
const change = (over: Record<string, unknown> = {}) => ({
  id: "c1",
  title: "Add TCS to your watchlist",
  detail: null,
  note: null,
  why: "You asked to keep an eye on it.",
  ...over,
});
const poll = (over: Partial<AgentPoll> = {}): AgentPoll => ({
  status: "running",
  events: [],
  next: 0,
  pending: [],
  result: null,
  error: null,
  ...over,
});
const reply = (text: string, over: Record<string, unknown> = {}) => ({
  reply: text,
  steps: [],
  proposals: [],
  mode: "ai",
  provider: "openai",
  model: "gpt-x",
  error: null,
  conversation_id: "chat-9",
  saved: true,
  ...over,
});

interface Script {
  polls: AgentPoll[];
  starts: unknown[];
  decisions: { path: string; body: unknown }[];
  stops: string[];
  startError?: unknown;
  /** Answers each look itself, so a test can hold the run at one stage. */
  next?: () => AgentPoll;
}

function engine(polls: AgentPoll[], extra: Partial<Script> = {}): Script {
  const script: Script = { polls, starts: [], decisions: [], stops: [], ...extra };
  serveApi((method, path, body) => {
    if (method === "POST" && path === RUNS) {
      if (script.startError) throw script.startError;
      script.starts.push(body);
      return { run_id: "run1" };
    }
    if (method === "GET" && path.startsWith(`${RUNS}/run1`)) {
      if (script.next) return script.next();
      return script.polls.length > 1 ? script.polls.shift() : script.polls[0];
    }
    if (method === "POST" && path.includes("/decisions/")) {
      script.decisions.push({ path, body });
      return { text: "ok" };
    }
    if (method === "DELETE") {
      script.stops.push(path);
      return { cancelled: true };
    }
    if (method === "GET" && path === STATUS) {
      return {
        ai_ready: true,
        apps: [],
        ai: { source: "cli", cli: null, api: null, fallback: true },
        providers: [{ id: "openai", label: "OpenAI", ready: true }],
        defaults: { speed: "balanced", helpers: 1 },
      };
    }
    throw new Error(`Unexpected call: ${method} ${path}`);
  });
  return script;
}

const agentRadio = () => screen.getByRole("radio", { name: "Agent" });

async function inAgentMode() {
  renderApp(<Shell />);
  openDrawer();
  await screen.findByRole("dialog");
  fireEvent.click(agentRadio());
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

describe("choosing agent mode", () => {
  it("starts in Chat, switches to Agent, and says in the box what to write", async () => {
    engine([poll()]);
    renderApp(<Shell />);
    openDrawer();
    await screen.findByRole("dialog");
    expect(screen.getByRole("radio", { name: "Chat" })).toBeChecked();
    expect(box()).toHaveAttribute("placeholder", "Ask about a stock");
    fireEvent.click(agentRadio());
    expect(agentRadio()).toBeChecked();
    expect(box().getAttribute("placeholder")).toMatch(/^Describe a task/);
  });

  it("sends a task to the run route, not to the chat route", async () => {
    const script = engine([poll({ status: "done", result: reply("Done.") })]);
    await inAgentMode();
    await say("check TCS");
    await waitFor(() => expect(script.starts).toHaveLength(1));
    expect(script.starts[0]).toEqual({
      messages: [{ role: "user", content: "check TCS" }],
      page: "/stock/TCS",
      agent_id: null,
      conversation_id: "new",
    });
    expect(callsTo("POST", CHAT)).toHaveLength(0);
  });

  it("carries the choices made in Ways to answer, including how many work on the task", async () => {
    const script = engine([poll({ status: "done", result: reply("Done.") })]);
    await inAgentMode();
    fireEvent.click(screen.getByRole("button", { name: /Ways to answer/ }));
    const team = await screen.findByRole("combobox", { name: "Who works on the task" });
    fireEvent.change(team, { target: { value: "3" } });
    fireEvent.click(screen.getByRole("radio", { name: "Careful" }));
    await say("compare TCS and INFY");
    await waitFor(() => expect(script.starts).toHaveLength(1));
    expect((script.starts[0] as { prefs: unknown }).prefs).toEqual({ speed: "careful", helpers: 3 });
  });

  it("offers the team choice only in agent mode", async () => {
    engine([poll()]);
    renderApp(<Shell />);
    openDrawer();
    await screen.findByRole("dialog");
    fireEvent.click(screen.getByRole("button", { name: /Ways to answer/ }));
    await screen.findByRole("combobox", { name: "Which AI" });
    expect(screen.queryByRole("combobox", { name: "Who works on the task" })).toBeNull();
    fireEvent.click(agentRadio());
    expect(await screen.findByRole("combobox", { name: "Who works on the task" })).toBeInTheDocument();
  });
});

describe("a task in progress", () => {
  it("shows each step as it happens and the final answer when it is done", async () => {
    const stages = [
      poll({ events: [event(1, "Price facts: TCS facts as of today")], next: 1 }),
      poll({ events: [event(2, "Helper 1 is looking into: News", "helper")], next: 2 }),
      poll({ status: "done", next: 2, result: reply("TCS looks steady. This is information, not advice.") }),
    ];
    let stage = 0;
    engine([], { next: () => stages[stage] as AgentPoll });
    await inAgentMode();
    await say("check TCS");
    expect(await screen.findByText("Price facts: TCS facts as of today")).toBeInTheDocument();
    stage = 1;
    expect(await screen.findByText("Helper 1 is looking into: News")).toBeInTheDocument();
    expect(screen.getByText("Price facts: TCS facts as of today")).toBeInTheDocument(); // earlier steps stay
    stage = 2;
    expect(await screen.findByText("TCS looks steady. This is information, not advice.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("region", { name: "What the Copilot is doing" })).toBeNull());
  });

  it("asks before it changes anything, and a press of Approve sends the answer once", async () => {
    const waiting = poll({
      status: "waiting",
      events: [event(1, "Add TCS to your watchlist", "action_request")],
      next: 1,
      pending: [change({ note: "This counts as test number 5 you have run." })],
    });
    const script = engine([waiting]);
    await inAgentMode();
    await say("add TCS");
    const card = await screen.findByRole("group", { name: "Change to decide: Add TCS to your watchlist" });
    expect(within(card).getByText("Why the Copilot asks: You asked to keep an eye on it.")).toBeInTheDocument();
    expect(within(card).getByText("This counts as test number 5 you have run.")).toBeInTheDocument();
    expect(screen.getByText("Waiting for you to decide")).toBeInTheDocument();
    expect(screen.getByText("Asked: Add TCS to your watchlist")).toBeInTheDocument();
    expect(script.decisions).toEqual([]); // nothing is sent until the person decides
    const approve = within(card).getByRole("button", { name: /^Approve/ });
    fireEvent.click(approve);
    fireEvent.click(approve);
    await waitFor(() => expect(script.decisions).toHaveLength(1));
    expect(script.decisions[0]).toEqual({ path: `${RUNS}/run1/decisions/c1`, body: { approve: true } });
    expect(approve).toBeDisabled();
    expect(within(card).getByRole("button", { name: /^Skip/ })).toBeDisabled();
  });

  it("sends Skip as a no", async () => {
    const script = engine([poll({ status: "waiting", pending: [change()] })]);
    await inAgentMode();
    await say("add TCS");
    fireEvent.click(await screen.findByRole("button", { name: /^Skip/ }));
    await waitFor(() => expect(script.decisions[0]?.body).toEqual({ approve: false }));
  });

  it("carries on after the change is answered and shows the result with its button", async () => {
    const polls = [
      poll({ status: "waiting", pending: [change()], next: 1, events: [event(1, "Add TCS to your watchlist", "action_request")] }),
      poll({ next: 2, events: [event(2, "TCS is on your watchlist now.", "action_result")] }),
      poll({
        status: "done",
        next: 2,
        result: reply("I added TCS.", { proposals: [{ kind: "navigate", label: "Open your watchlist", path: "/", symbol: null }] }),
      }),
    ];
    engine(polls);
    await inAgentMode();
    await say("add TCS");
    fireEvent.click(await screen.findByRole("button", { name: /^Approve/ }));
    expect(await screen.findByText("I added TCS.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open your watchlist" })).toBeInTheDocument();
  });

  it("stops a task, and shows what was found before it was stopped", async () => {
    const polls = [
      poll({ events: [event(1, "Price facts: TCS")], next: 1 }),
      poll({ status: "cancelled", next: 1, result: reply("You stopped this run, so here is what I found so far:\n- Price facts: TCS") }),
    ];
    const script = engine(polls);
    await inAgentMode();
    await say("check TCS");
    fireEvent.click(await screen.findByRole("button", { name: "Stop" }));
    await waitFor(() => expect(script.stops).toEqual([`${RUNS}/run1`]));
    expect(await screen.findByText(/You stopped this run, so here is what I found so far/)).toBeInTheDocument();
  });

  it("says plainly that it was stopped when nothing came back", async () => {
    engine([poll({ status: "cancelled", result: null })]);
    await inAgentMode();
    await say("check TCS");
    expect(await screen.findByText("You stopped this run before it finished.", {}, { timeout: 3000 })).toBeInTheDocument();
  });

  it("cannot be switched to Chat in the middle of a task", async () => {
    engine([poll({ events: [event(1, "Price facts: TCS")], next: 1 })]);
    await inAgentMode();
    await say("check TCS");
    await screen.findByText("Price facts: TCS");
    expect(screen.getByRole("radio", { name: "Chat" })).toBeDisabled();
  });

  it("starting a new chat stops the task and clears it", async () => {
    const script = engine([poll({ events: [event(1, "Price facts: TCS")], next: 1 })]);
    await inAgentMode();
    await say("check TCS");
    await screen.findByText("Price facts: TCS");
    fireEvent.click(screen.getByRole("button", { name: /New chat/ }));
    await waitFor(() => expect(script.stops).toEqual([`${RUNS}/run1`]));
    await waitFor(() => expect(screen.queryByText("Price facts: TCS")).toBeNull());
  });
});

describe("when something goes wrong", () => {
  it("shows the engine's own sentence when it will not start, and puts the message back", async () => {
    engine([poll()], {
      startError: new ApiError("NO_AI_KEY", "No AI is set up yet. Open Settings, then AI assistants, and pick one.", 422),
    });
    await inAgentMode();
    await say("check TCS");
    expect(await screen.findByText(/No AI is set up yet/)).toBeInTheDocument();
    await waitFor(() => expect(box()).toHaveValue("check TCS"));
  });

  it("offers a retry when the task fails", async () => {
    engine([poll({ status: "failed", error: "The Copilot could not finish this." })]);
    await inAgentMode();
    await say("check TCS");
    expect(await screen.findByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.getByText(/could not answer just now/)).toBeInTheDocument();
  });

  it("uses no developer word", async () => {
    engine([poll({ status: "waiting", pending: [change()] })]);
    await inAgentMode();
    await say("add TCS");
    await screen.findByRole("group", { name: /Change to decide/ });
    expect(document.body.textContent).not.toMatch(/\b(API|token|terminal|command|CLI|JSON|agent id)\b/i);
  });
});
