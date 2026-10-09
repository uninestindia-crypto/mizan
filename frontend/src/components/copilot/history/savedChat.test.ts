import { describe, expect, it } from "vitest";
import type { ChatDetail } from "../../../lib/copilotHistory";
import { savedMessages } from "./savedChat";

const steps = [{ label: "Halal screening", summary: "AAA: checked", ok: true }];
const proposals = [{ kind: "navigate", label: "Open AAA", path: "/stock/AAA", symbol: "AAA" }];

const detail: ChatDetail = {
  id: "c1",
  title: "is AAA halal?",
  turns: [
    { role: "user", content: "is AAA halal?", meta: {} },
    { role: "assistant", content: "AAA passes.", meta: { mode: "ai", provider: "cli:claude", steps, proposals } },
    { role: "assistant", content: "Built in.", meta: { mode: "built_in", error: "The AI could not be reached." } },
  ],
};

describe("a saved chat read back into the thread", () => {
  const [user, answer, builtIn] = savedMessages(detail);

  it("keeps what the person said as it was", () => {
    expect(user).toEqual({ role: "user", content: "is AAA halal?" });
  });

  it("gives an answer back its steps, buttons and who answered, as the live reply had them", () => {
    expect(answer).toMatchObject({ role: "assistant", content: "AAA passes.", mode: "ai", provider: "cli:claude" });
    expect(answer).toMatchObject({ steps, proposals, savedNote: null });
  });

  it("keeps a built-in answer built in, with the note it carried", () => {
    expect(builtIn).toMatchObject({ mode: "built_in", provider: null, error: "The AI could not be reached." });
  });

  it("reads an answer saved with no details as a plain built-in answer", () => {
    const [plain] = savedMessages({ id: "c", title: "t", turns: [{ role: "assistant", content: "Hi", meta: {} }] });
    expect(plain).toMatchObject({ content: "Hi", mode: "built_in", steps: [], proposals: [] });
  });

  it("drops a button that leads outside the app, as a live reply does", () => {
    const bad = { kind: "navigate", label: "Go", path: "https://evil.example", symbol: null };
    const turn = { role: "assistant" as const, content: "x", meta: { proposals: [bad] } };
    const [kept] = savedMessages({ id: "c", title: "t", turns: [turn] });
    expect(kept).toMatchObject({ proposals: [] });
  });
});
