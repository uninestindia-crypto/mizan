import { describe, expect, it } from "vitest";
import { type ChatReply, normaliseReply } from "../../lib/copilot";
import {
  type AssistantMessage,
  type ChatAction,
  type ChatState,
  chatReducer,
  initialChat,
  keyHelp,
  replyExplainsKeys,
  visibleProposals,
} from "./chatState";

const run = (actions: ChatAction[], from: ChatState = initialChat): ChatState => actions.reduce(chatReducer, from);
const reply = (text: string) => normaliseReply({ reply: text, mode: "ai", provider: "openai", model: "m" });

describe("the buttons under a reply", () => {
  const addKey = { kind: "navigate" as const, label: "Add an AI key", path: "/settings/accounts", symbol: null };
  const openTcs = { kind: "navigate" as const, label: "Open TCS", path: "/stock/TCS", symbol: "TCS" };
  const answered = (mode: "ai" | "built_in") => {
    const proposals = [addKey, openTcs];
    const state = run([
      { type: "sent", content: "hi", requestId: 1 },
      { type: "replied", requestId: 1, reply: { ...reply("x"), mode, proposals } },
    ]);
    return state.messages[1] as AssistantMessage;
  };

  it("leaves out a second Add an AI key button when the built-in line already offers it", () => {
    expect(visibleProposals(answered("built_in"))).toEqual([openTcs]);
  });

  it("shows every button when an AI model answered", () => {
    expect(visibleProposals(answered("ai"))).toEqual([addKey, openTcs]);
  });
});

describe("when a reply already talks about AI keys", () => {
  const addKey = { kind: "navigate" as const, label: "Add an AI key", path: "/settings/accounts", symbol: null };
  const make = (text: string, mode: "ai" | "built_in", proposals: ChatReply["proposals"] = []) => {
    const state = run([
      { type: "sent", content: "hi", requestId: 1 },
      { type: "replied", requestId: 1, reply: { ...reply(text), mode, proposals } },
    ]);
    return state.messages[1] as AssistantMessage;
  };
  const NEED_AI = "To ask open-ended questions, add an AI key: open Settings, then Accounts and keys.";
  const REJECTED = "That AI service did not accept your key. Open Settings, then Accounts and keys, and check it.";

  it("recognises the engine's own key sentences", () => {
    expect(replyExplainsKeys(`Which stock?\n\n${NEED_AI}`)).toBe(true);
    expect(replyExplainsKeys(REJECTED)).toBe(true);
    expect(replyExplainsKeys("TCS passes both standards. Key ratios are below.")).toBe(false);
  });

  it("adds a note and a button of its own only when the reply says nothing about keys", () => {
    expect(keyHelp(make("Which stock?", "built_in"))).toBe("footer");
    expect(keyHelp(make("Which stock?", "ai"))).toBe("none");
  });

  it("adds no note when the reply already says to add a key, and keeps the engine's one button", () => {
    const message = make(`Which stock?\n\n${NEED_AI}`, "built_in", [addKey]);
    expect(keyHelp(message)).toBe("none");
    expect(visibleProposals(message)).toEqual([addKey]);
  });

  it("adds no note after a rejected key either, but makes sure there is one clear button", () => {
    const withButton = make(REJECTED, "built_in", [addKey]);
    expect(keyHelp(withButton)).toBe("none");
    expect(keyHelp(make(REJECTED, "built_in"))).toBe("button");
  });
});

describe("a message the engine refuses", () => {
  it("takes the refused message out of the conversation and keeps the engine's sentence", () => {
    const state = run([
      { type: "sent", content: "hi", requestId: 1 },
      { type: "failed", requestId: 1, refusal: "Your message is too long." },
    ]);
    expect(state).toMatchObject({ status: "failed", failure: "Your message is too long.", messages: [] });
  });

  it("keeps the question after any other failure, with no sentence of its own", () => {
    const state = run([
      { type: "sent", content: "hi", requestId: 1 },
      { type: "failed", requestId: 1 },
    ]);
    expect(state).toMatchObject({ status: "failed", failure: null });
    expect(state.messages).toHaveLength(1);
  });

  it("forgets the sentence when the person sends something new", () => {
    const state = run([
      { type: "sent", content: "hi", requestId: 1 },
      { type: "failed", requestId: 1, refusal: "Too long." },
      { type: "sent", content: "shorter", requestId: 2 },
    ]);
    expect(state).toMatchObject({ status: "thinking", failure: null });
  });
});

describe("the conversation", () => {
  it("adds what the person said and waits for the answer", () => {
    const state = run([{ type: "sent", content: "Is TCS halal?", requestId: 1 }]);
    expect(state.status).toBe("thinking");
    expect(state.messages).toMatchObject([{ role: "user", content: "Is TCS halal?" }]);
  });

  it("adds the answer for the request it is waiting on", () => {
    const state = run([
      { type: "sent", content: "hi", requestId: 1 },
      { type: "replied", requestId: 1, reply: reply("Hello") },
    ]);
    expect(state.status).toBe("idle");
    expect(state.messages.map((m) => [m.role, m.content])).toEqual([
      ["user", "hi"],
      ["assistant", "Hello"],
    ]);
    expect(state.messages[1]).toMatchObject({ mode: "ai", provider: "openai", steps: [], proposals: [] });
  });

  it("sends nothing while an answer is awaited, and nothing empty", () => {
    const waiting = run([{ type: "sent", content: "one", requestId: 1 }]);
    expect(chatReducer(waiting, { type: "sent", content: "two", requestId: 2 })).toBe(waiting);
    expect(chatReducer(initialChat, { type: "sent", content: "   ", requestId: 1 })).toBe(initialChat);
  });

  it("ignores an answer that arrives after New chat", () => {
    const state = run([
      { type: "sent", content: "hi", requestId: 1 },
      { type: "cleared" },
      { type: "replied", requestId: 1, reply: reply("late") },
    ]);
    expect(state.messages).toEqual([]);
    expect(state.status).toBe("idle");
  });

  it("keeps the question after a failure so it can be tried again", () => {
    const failed = run([
      { type: "sent", content: "hi", requestId: 1 },
      { type: "failed", requestId: 1 },
    ]);
    expect(failed.status).toBe("failed");
    expect(failed.messages).toHaveLength(1);
    const again = chatReducer(failed, { type: "retried", requestId: 2 });
    expect(again.status).toBe("thinking");
    expect(again.pending).toBe(2);
    expect(again.messages).toHaveLength(1);
  });

  it("does not retry when nothing failed", () => {
    expect(chatReducer(initialChat, { type: "retried", requestId: 1 })).toBe(initialChat);
  });

  it("ignores a failure for an old request", () => {
    const state = run([{ type: "sent", content: "hi", requestId: 2 }]);
    expect(chatReducer(state, { type: "failed", requestId: 1 })).toBe(state);
  });

  it("gives every message its own id", () => {
    const state = run([
      { type: "sent", content: "a", requestId: 1 },
      { type: "replied", requestId: 1, reply: reply("b") },
      { type: "sent", content: "c", requestId: 2 },
    ]);
    expect(new Set(state.messages.map((m) => m.id)).size).toBe(3);
  });
});
