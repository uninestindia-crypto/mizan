import { describe, expect, it } from "vitest";
import { normaliseReply } from "../../lib/copilot";
import {
  type AssistantMessage,
  type ChatAction,
  type ChatState,
  chatReducer,
  initialChat,
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
