import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../../lib/api";
import { chatWith, openDrawer, reply, say, Shell } from "../chatTestKit";
import { renderApp } from "../testHarness";

vi.mock("../../../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../lib/api")>();
  return { ...original, api: vi.fn() };
});

beforeEach(() => {
  vi.mocked(api).mockReset();
  window.localStorage.clear();
});

afterEach(cleanup);

async function ask(answer: unknown) {
  chatWith(answer);
  renderApp(<Shell />);
  openDrawer();
  await screen.findByRole("dialog");
  await say("question");
}

const NAMED: [string, string][] = [
  ["cli:claude", "Answered by Claude Code"],
  ["cli:codex", "Answered by Codex"],
  ["cli:antigravity", "Answered by Antigravity"],
  ["anthropic", "Answered by Claude (Anthropic)"],
  ["openai", "Answered by OpenAI"],
  ["gemini", "Answered by Google Gemini"],
  ["groq", "Answered by Groq"],
  ["deepseek", "Answered by DeepSeek"],
  ["mistral", "Answered by Mistral"],
  ["openrouter", "Answered by OpenRouter"],
];
const UNNAMED: [string | null][] = [["acme-ai"], ["cli:unknown"], [null]];

describe("which AI answered, under an answer", () => {
  it.each(NAMED)("names %s", async (provider, line) => {
    await ask(reply({ provider, model: null }));
    expect(await screen.findByText(line)).toBeInTheDocument();
  });

  it("is happy with no model named at all, as for an AI app on this computer", async () => {
    await ask(reply({ provider: "cli:claude", model: null }));
    expect(await screen.findByText("Answered by Claude Code")).toBeInTheDocument();
  });

  it.each(UNNAMED)("says nothing for %s, and never a model's id", async (provider) => {
    await ask(reply({ provider, model: "secret-model-9" }));
    await screen.findByText("TCS passes both standards.");
    expect(screen.queryByText(/Answered by/)).toBeNull();
    expect(screen.queryByText(/secret-model-9/)).toBeNull();
  });

  it("leaves a built-in answer's own note as it is", async () => {
    await ask(reply({ mode: "built_in", provider: null, model: null }));
    expect(await screen.findByText(/Answered from QuantOS's built-in answers\./)).toBeInTheDocument();
    expect(screen.queryByText(/^Answered by/)).toBeNull();
  });
});

describe("when an answer could not be saved", () => {
  const note = "This chat is full. Start a new chat to keep saving.";
  const unsaved = reply({ saved: false, saved_note: note, conversation_id: "full-chat" });

  it("still shows the answer, with the engine's sentence quietly under it and no alarm", async () => {
    await ask(unsaved);
    expect(await screen.findByText("TCS passes both standards.")).toBeInTheDocument();
    expect(screen.getByText(note)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("says it once, not under every answer that follows", async () => {
    chatWith(unsaved, unsaved, unsaved);
    renderApp(<Shell />);
    openDrawer();
    await screen.findByRole("dialog");
    await say("one");
    await screen.findByText("TCS passes both standards.");
    await say("two");
    await waitFor(() => expect(screen.getAllByText("TCS passes both standards.")).toHaveLength(2));
    await say("three");
    await waitFor(() => expect(screen.getAllByText("TCS passes both standards.")).toHaveLength(3));
    expect(screen.getAllByText(note)).toHaveLength(1);
  });

  it("says nothing when the chat was saved", async () => {
    await ask(reply({ saved: true, conversation_id: "ok" }));
    await screen.findByText("TCS passes both standards.");
    expect(screen.queryByText(/could not be saved|is full/)).toBeNull();
  });
});

describe("the button that chooses an AI", () => {
  const choose = { kind: "navigate", label: "Choose an AI", path: "/settings/ai", symbol: null };

  it("takes the person to the AI choices in Settings", async () => {
    const text = "I need an AI for that. Open Settings, then AI assistants, and pick one.";
    await ask(reply({ reply: text, mode: "built_in", provider: null, model: null, proposals: [choose] }));
    fireEvent.click(await screen.findByRole("button", { name: "Choose an AI" }));
    await waitFor(() => expect(screen.getByTestId("path")).toHaveTextContent("/settings/ai"));
    expect(screen.queryByText(/Add an AI key/)).toBeNull();
  });

  it("is added once when the reply talks about choosing an AI and the engine sent no button", async () => {
    const text = "To ask open-ended questions, set up an AI: open Settings, then AI assistants.";
    await ask(reply({ reply: text, mode: "built_in", provider: null, model: null }));
    fireEvent.click(await screen.findByRole("button", { name: "Choose an AI" }));
    await waitFor(() => expect(screen.getByTestId("path")).toHaveTextContent("/settings/ai"));
  });

  it("is still the one button when the engine sends the old label, which goes where it always went", async () => {
    const old = { kind: "navigate", label: "Add an AI key", path: "/settings/accounts", symbol: null };
    const text = "Which stock?\n\nTo ask open-ended questions, add an AI key: open Settings, then Accounts and keys.";
    await ask(reply({ reply: text, mode: "built_in", provider: null, model: null, proposals: [old] }));
    fireEvent.click(await screen.findByRole("button", { name: "Add an AI key" }));
    await waitFor(() => expect(screen.getByTestId("path")).toHaveTextContent("/settings/accounts"));
  });
});
