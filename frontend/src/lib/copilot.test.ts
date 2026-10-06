import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";
import {
  buildChatRequest,
  buildVerifyRequest,
  copilotApi,
  defaultSelection,
  EMPTY_REPLY,
  HISTORY_LIMIT,
  isSafeAppPath,
  isValidSymbol,
  normaliseReply,
  openSecondOpinion,
  readSecondOpinionRequest,
  SECOND_OPINION_EVENT,
} from "./copilot";

vi.mock("./api", async (importOriginal) => ({ ...(await importOriginal<typeof import("./api")>()), api: vi.fn() }));

describe("the chat request", () => {
  it("sends the last few turns and the screen the person is on", () => {
    const turns = Array.from({ length: 12 }, (_, i) => ({
      role: i % 2 === 0 ? ("user" as const) : ("assistant" as const),
      content: `m${i}`,
    }));
    const request = buildChatRequest(turns, "/stock/TCS");
    expect(request.page).toBe("/stock/TCS");
    expect(request.agent_id).toBeNull();
    expect(request.messages.length).toBeLessThanOrEqual(HISTORY_LIMIT);
    expect(request.messages[0]?.content).toBe("m4");
    expect(request.messages.at(-1)?.content).toBe("m11");
  });

  it("always starts with something the person said", () => {
    const request = buildChatRequest(
      [
        { role: "assistant", content: "Hello" },
        { role: "user", content: "Is TCS halal?" },
      ],
      null,
    );
    expect(request.messages).toEqual([{ role: "user", content: "Is TCS halal?" }]);
  });

  it("sends only role and content, even when the turns carry more", () => {
    const turn = { role: "user" as const, content: "hi", id: 4, secret: "x" };
    expect(buildChatRequest([turn], null).messages).toEqual([{ role: "user", content: "hi" }]);
  });

  it("keeps each turn within what the engine accepts", () => {
    const long = "x".repeat(9000);
    const request = buildChatRequest([{ role: "user", content: long }], null);
    expect(request.messages[0]?.content).toHaveLength(4000);
  });

  it("drops a page that is not a path inside the app", () => {
    for (const page of ["https://evil.example/", "//evil.example", "stock/TCS", ""]) {
      expect(buildChatRequest([{ role: "user", content: "hi" }], page).page).toBeNull();
    }
  });
});

describe("paths and symbols from the engine", () => {
  it("accepts only paths inside the app", () => {
    expect(isSafeAppPath("/stock/TCS")).toBe(true);
    expect(isSafeAppPath("/settings/accounts")).toBe(true);
    for (const path of ["https://x.test", "//x.test", "javascript:alert(1)", "/a b", "/a\\b", "", null, 5]) {
      expect(isSafeAppPath(path)).toBe(false);
    }
  });

  it("accepts NSE style symbols and nothing that could carry markup", () => {
    for (const symbol of ["TCS", "M&M", "BAJAJ-AUTO", "L&TFH"]) expect(isValidSymbol(symbol)).toBe(true);
    for (const symbol of ["", "<script>", "TCS HALAL", "TCS.NS", "a".repeat(16), undefined]) {
      expect(isValidSymbol(symbol)).toBe(false);
    }
    expect(isValidSymbol("a".repeat(15))).toBe(true);
  });
});

describe("cleaning the engine's reply", () => {
  it("fills in what is missing instead of failing", () => {
    const reply = normaliseReply({ reply: "Hello" });
    expect(reply).toMatchObject({
      reply: "Hello",
      steps: [],
      proposals: [],
      mode: "built_in",
      provider: null,
      model: null,
      error: null,
    });
  });

  it("says something kind when the reply is empty", () => {
    expect(normaliseReply({ reply: "   " }).reply).toBe(EMPTY_REPLY);
    expect(normaliseReply(null).reply).toBe(EMPTY_REPLY);
  });

  it("keeps working lookups and marks failed ones", () => {
    const reply = normaliseReply({
      reply: "x",
      steps: [
        { label: "Halal screening", summary: "TCS: both standards checked", ok: true },
        { label: "News", summary: "", ok: false },
        { summary: "no label" } as never,
      ],
    });
    expect(reply.steps).toEqual([
      { label: "Halal screening", summary: "TCS: both standards checked", ok: true },
      { label: "News", summary: "", ok: false },
    ]);
  });

  it("keeps only buttons the screen can safely act on", () => {
    const reply = normaliseReply({
      reply: "x",
      proposals: [
        { kind: "navigate", label: "Open TCS", path: "/stock/TCS", symbol: "TCS" },
        { kind: "navigate", label: "Elsewhere", path: "https://evil.example", symbol: null },
        { kind: "second_opinion", label: "", path: null, symbol: "infy" },
        { kind: "second_opinion", label: "Bad", path: null, symbol: "<b>" },
        { kind: "buy", label: "Buy", path: null, symbol: "TCS" } as never,
      ],
    });
    expect(reply.proposals.map((p) => [p.kind, p.label, p.path, p.symbol])).toEqual([
      ["navigate", "Open TCS", "/stock/TCS", "TCS"],
      ["second_opinion", "Get a second opinion on INFY", null, "INFY"],
    ]);
  });

  it("reads the mode and the model that answered", () => {
    const reply = normaliseReply({ reply: "x", mode: "ai", provider: "openai", model: "m" });
    expect(reply).toMatchObject({ mode: "ai", provider: "openai", model: "m" });
    expect(normaliseReply({ reply: "x", mode: "nonsense" as never }).mode).toBe("built_in");
  });
});

describe("the second opinion request", () => {
  it("asks for the reordered recheck and adds the pick note only when given", () => {
    const plain = { symbol: "TCS", providers: ["openai"], recheck: true };
    expect(buildVerifyRequest("tcs", ["openai"], null)).toEqual(plain);
    expect(buildVerifyRequest("TCS", ["openai", "anthropic"], " Ranked 3rd ")).toEqual({
      symbol: "TCS",
      providers: ["openai", "anthropic"],
      recheck: true,
      pick_note: "Ranked 3rd",
    });
  });

  it("keeps the pick note and the model list within what the engine accepts", () => {
    const request = buildVerifyRequest("TCS", ["a", "b", "c", "d", "e", "f", "g"], "n".repeat(500));
    expect(request.pick_note).toHaveLength(300);
    expect(request.providers).toHaveLength(6);
  });

  it("ticks up to three ready models at first and never one without a key", () => {
    const models = [
      { id: "a", label: "A", ready: true },
      { id: "b", label: "B", ready: false },
      { id: "c", label: "C", ready: true },
      { id: "d", label: "D", ready: true },
      { id: "e", label: "E", ready: true },
    ];
    expect(defaultSelection(models)).toEqual(["a", "c", "d"]);
    expect(defaultSelection([{ id: "b", label: "B", ready: false }])).toEqual([]);
  });
});

describe("opening the second opinion from anywhere", () => {
  const seen: Event[] = [];
  const listener = (event: Event) => seen.push(event);
  beforeEach(() => {
    seen.length = 0;
    window.addEventListener(SECOND_OPINION_EVENT, listener);
  });
  afterEach(() => window.removeEventListener(SECOND_OPINION_EVENT, listener));

  it("uses the shared event name and a detail with the symbol", () => {
    openSecondOpinion("TCS");
    expect(SECOND_OPINION_EVENT).toBe("quantos:second-opinion");
    expect(seen).toHaveLength(1);
    expect((seen[0] as CustomEvent).detail).toEqual({ symbol: "TCS" });
  });

  it("carries the platform's pick note when the opener has one", () => {
    openSecondOpinion("TCS", "Ranked 3rd of 40");
    expect(readSecondOpinionRequest(seen[0] as Event)).toEqual({ symbol: "TCS", pickNote: "Ranked 3rd of 40" });
  });

  it("reads a request from the plain shape another screen sends", () => {
    const event = new CustomEvent(SECOND_OPINION_EVENT, { detail: { symbol: "infy" } });
    expect(readSecondOpinionRequest(event)).toEqual({ symbol: "INFY" });
  });

  it("ignores a request whose detail is not a usable symbol", () => {
    for (const detail of [null, {}, { symbol: 5 }, { symbol: "<img src=x>" }, "TCS"]) {
      expect(readSecondOpinionRequest(new CustomEvent(SECOND_OPINION_EVENT, { detail }))).toBeNull();
    }
  });
});

describe("the engine calls", () => {
  beforeEach(() => {
    vi.mocked(api).mockReset();
  });

  it("posts the chat to the Copilot", async () => {
    vi.mocked(api).mockResolvedValue({ reply: "ok" });
    const body = buildChatRequest([{ role: "user", content: "hi" }], "/");
    await copilotApi.chat(body);
    expect(api).toHaveBeenCalledWith("/api/v2/copilot/chat", "POST", body);
  });

  it("lists models, keeping the ready flag exact", async () => {
    const listed = [
      { id: "openai", label: "OpenAI", ready: true },
      { id: "x", label: "", ready: "yes" },
      { label: "no id" },
    ];
    vi.mocked(api).mockResolvedValue({ models: listed });
    expect(await copilotApi.models()).toEqual([
      { id: "openai", label: "OpenAI", ready: true },
      { id: "x", label: "x", ready: false },
    ]);
  });

  it("starts and polls a run on the paths the contract names", async () => {
    vi.mocked(api).mockResolvedValue({ job_id: "abc" });
    await copilotApi.startVerify(buildVerifyRequest("TCS", ["openai"], null));
    const sent = { symbol: "TCS", providers: ["openai"], recheck: true };
    expect(api).toHaveBeenLastCalledWith("/api/v2/copilot/verify", "POST", sent);
    await copilotApi.pollVerify("a/b");
    expect(api).toHaveBeenLastCalledWith("/api/v2/copilot/verify/a%2Fb");
  });
});
