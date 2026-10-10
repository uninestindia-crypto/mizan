import { beforeEach, describe, expect, it, vi } from "vitest";
import { agentApi, type AgentPoll, type AgentView, answering, applyPoll, progressWords, STARTING } from "./agentRun";
import { api } from "./api";
import { NO_PREFS } from "./answerPrefs";

vi.mock("./api", async (importOriginal) => {
  const original = await importOriginal<typeof import("./api")>();
  return { ...original, api: vi.fn() };
});

const event = (n: number, text = `line ${n}`) => ({ n, kind: "step", text, ok: true });
const change = (id: string) => ({ id, title: `Change ${id}`, detail: null, note: null, why: "" });
const poll = (over: Partial<AgentPoll> = {}): AgentPoll => ({
  status: "running",
  events: [],
  next: 0,
  pending: [],
  result: null,
  error: null,
  ...over,
});
const view = (over: Partial<AgentView> = {}): AgentView => ({ ...STARTING, runId: "r1", ...over });

beforeEach(() => vi.mocked(api).mockReset());

describe("following a run", () => {
  it("adds only the lines it has not seen, in order", () => {
    const first = applyPoll(view(), poll({ events: [event(1), event(2)], next: 2 }));
    expect(first.events.map((e) => e.n)).toEqual([1, 2]);
    const again = applyPoll(first, poll({ events: [event(2), event(3)], next: 3 }));
    expect(again.events.map((e) => e.n)).toEqual([1, 2, 3]);
  });

  it("shows exactly the changes that wait for the person now, and drops answered ones from the busy list", () => {
    const waiting = applyPoll(view(), poll({ status: "waiting", pending: [change("a"), change("b")] }));
    expect(waiting.status).toBe("waiting");
    expect(waiting.pending.map((c) => c.id)).toEqual(["a", "b"]);
    const pressed = answering(answering(waiting, "a"), "a");
    expect(pressed.answering).toEqual(["a"]); // a second press is not remembered twice
    const later = applyPoll(pressed, poll({ pending: [change("b")] }));
    expect(later.pending.map((c) => c.id)).toEqual(["b"]);
    expect(later.answering).toEqual([]);
  });
});

describe("the words beside the spinner", () => {
  it("say what is happening", () => {
    expect(progressWords(STARTING)).toBe("Getting started…");
    expect(progressWords(view({ events: [event(1)] }))).toBe("Working on it…");
    expect(progressWords(view({ pending: [change("a")] }))).toBe("Waiting for you to decide");
    expect(progressWords(view({ stopping: true, pending: [change("a")] }))).toBe("Stopping…");
  });
});

describe("asking the engine", () => {
  it("starts a task with the last turns, the page, the chat and only the choices that were made", async () => {
    vi.mocked(api).mockResolvedValue({ run_id: "r9" });
    const turns = [{ role: "user" as const, content: "check TCS" }];
    await expect(agentApi.start(turns, "/stock/TCS", null, NO_PREFS)).resolves.toEqual({ run_id: "r9" });
    await agentApi.start(turns, null, "chat-1", { ...NO_PREFS, speed: "careful", helpers: 2 });
    const [first, second] = vi.mocked(api).mock.calls;
    expect(first).toEqual([
      "/api/v2/copilot/agent/runs",
      "POST",
      { messages: turns, page: "/stock/TCS", agent_id: null, conversation_id: "new" },
    ]);
    expect(second?.[2]).toEqual({
      messages: turns,
      page: null,
      agent_id: null,
      conversation_id: "chat-1",
      prefs: { speed: "careful", helpers: 2 },
    });
  });

  it("looks, stops and answers by the run's own address", async () => {
    vi.mocked(api).mockResolvedValue({});
    await agentApi.poll("a b", 4);
    await agentApi.stop("a b");
    await agentApi.decide("a b", "x/y", false);
    expect(vi.mocked(api).mock.calls).toEqual([
      ["/api/v2/copilot/agent/runs/a%20b?after=4"],
      ["/api/v2/copilot/agent/runs/a%20b", "DELETE"],
      ["/api/v2/copilot/agent/runs/a%20b/decisions/x%2Fy", "POST", { approve: false }],
    ]);
  });
});
