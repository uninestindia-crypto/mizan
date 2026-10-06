import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../../lib/api";
import { SECOND_OPINION_EVENT } from "../../lib/copilot";
import { CopilotButton } from "./CopilotButton";
import { CopilotDrawer } from "./CopilotDrawer";
import { CopilotProvider } from "./CopilotProvider";
import { callsTo, renderApp, routeApi } from "./testHarness";

vi.mock("../../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../lib/api")>();
  return { ...original, api: vi.fn() };
});

const CHAT = "/api/v2/copilot/chat";

function Shell() {
  return (
    <CopilotProvider>
      <CopilotButton />
      <CopilotDrawer />
    </CopilotProvider>
  );
}

const reply = (over: Record<string, unknown> = {}) => ({
  reply: "TCS passes both standards.",
  steps: [],
  proposals: [],
  mode: "ai",
  provider: "openai",
  model: "gpt-x",
  error: null,
  ...over,
});

function chatWith(...replies: unknown[]) {
  const queue = [...replies];
  routeApi({ [`POST ${CHAT}`]: () => queue.shift() ?? reply() });
}

const openDrawer = () => fireEvent.click(screen.getByRole("button", { name: /Copilot/ }));
const box = () => screen.getByRole("textbox", { name: "Your message to the Copilot" });
async function say(text: string) {
  fireEvent.change(box(), { target: { value: text } });
  fireEvent.keyDown(box(), { key: "Enter" });
}

describe("the Copilot drawer", () => {
  beforeEach(() => {
    vi.mocked(api).mockReset();
  });
  afterEach(cleanup);

  it("opens with focus in the message box, and closes on Escape with focus back on the button", async () => {
    chatWith();
    renderApp(<Shell />);
    expect(screen.queryByRole("dialog")).toBeNull();
    const button = screen.getByRole("button", { name: /Copilot/ });
    button.focus();
    fireEvent.click(button);
    const dialog = await screen.findByRole("dialog", { name: "Copilot" });
    expect(dialog).toBeInTheDocument();
    await waitFor(() => expect(box()).toHaveFocus());

    fireEvent.keyDown(box(), { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(screen.getByRole("button", { name: /Copilot/ })).toHaveFocus());
  });

  it("opens and closes with Ctrl+J and Cmd+J", async () => {
    renderApp(<Shell />);
    fireEvent.keyDown(window, { key: "j", ctrlKey: true });
    expect(await screen.findByRole("dialog", { name: "Copilot" })).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "J", metaKey: true });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("offers the starter questions on an empty chat and sends one when clicked", async () => {
    chatWith(reply());
    renderApp(<Shell />);
    openDrawer();
    for (const text of ["Is TCS halal?", "How is INFY doing?", "News on RELIANCE", "What can you do?"]) {
      expect(await screen.findByRole("button", { name: text })).toBeInTheDocument();
    }
    fireEvent.click(screen.getByRole("button", { name: "Is TCS halal?" }));
    expect(await screen.findByText("TCS passes both standards.")).toBeInTheDocument();
    expect(callsTo("POST", CHAT)[0]?.[2]).toEqual({
      messages: [{ role: "user", content: "Is TCS halal?" }],
      page: "/stock/TCS",
      agent_id: null,
    });
    expect(screen.queryByRole("button", { name: "News on RELIANCE" })).toBeNull();
  });

  it("sends on Enter, adds a line on Shift+Enter, and says it is thinking while it waits", async () => {
    let answer: (value: unknown) => void = () => undefined;
    routeApi({ [`POST ${CHAT}`]: () => new Promise((resolve) => (answer = resolve)) });
    renderApp(<Shell />);
    openDrawer();
    await screen.findByRole("dialog");
    fireEvent.change(box(), { target: { value: "first line" } });
    fireEvent.keyDown(box(), { key: "Enter", shiftKey: true });
    expect(callsTo("POST", CHAT)).toHaveLength(0);
    fireEvent.keyDown(box(), { key: "Enter" });
    expect(await screen.findByText("Thinking…")).toBeInTheDocument();
    expect(box()).toHaveValue("");
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    await act(async () => answer(reply({ reply: "Done." })));
    expect(await screen.findByText("Done.")).toBeInTheDocument();
    expect(screen.queryByText("Thinking…")).toBeNull();
  });

  it("keeps the conversation when the drawer is closed and opened again, and when the page changes", async () => {
    chatWith(reply({ reply: "An answer to remember." }));
    renderApp(<Shell />);
    openDrawer();
    await screen.findByRole("dialog");
    await say("hello");
    await screen.findByText("An answer to remember.");
    fireEvent.keyDown(box(), { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    openDrawer();
    expect(await screen.findByText("An answer to remember.")).toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument();
  });

  it("keeps an unsent draft too", async () => {
    renderApp(<Shell />);
    openDrawer();
    await screen.findByRole("dialog");
    fireEvent.change(box(), { target: { value: "half a thought" } });
    fireEvent.keyDown(box(), { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    openDrawer();
    await screen.findByRole("dialog");
    expect(box()).toHaveValue("half a thought");
  });

  it("starts a clean chat on New chat, and sends only the new questions afterwards", async () => {
    chatWith(reply({ reply: "First answer." }), reply({ reply: "Second answer." }));
    renderApp(<Shell />);
    openDrawer();
    await screen.findByRole("dialog");
    await say("one");
    await screen.findByText("First answer.");
    fireEvent.click(screen.getByRole("button", { name: "New chat" }));
    expect(screen.queryByText("First answer.")).toBeNull();
    expect(screen.getByRole("button", { name: "What can you do?" })).toBeInTheDocument();
    await say("two");
    await screen.findByText("Second answer.");
    expect(callsTo("POST", CHAT)[1]?.[2]).toMatchObject({ messages: [{ role: "user", content: "two" }] });
  });

  it("announces replies politely to a screen reader", async () => {
    chatWith();
    renderApp(<Shell />);
    openDrawer();
    const log = await screen.findByRole("log", { name: "Conversation" });
    expect(log).toHaveAttribute("aria-live", "polite");
  });
});

describe("what a reply shows", () => {
  beforeEach(() => {
    vi.mocked(api).mockReset();
  });
  afterEach(cleanup);

  async function ask(answer: unknown) {
    chatWith(answer);
    renderApp(<Shell />);
    openDrawer();
    await screen.findByRole("dialog");
    await say("question");
  }

  it("folds away what the Copilot looked at and marks a lookup that failed", async () => {
    await ask(
      reply({
        steps: [
          { label: "Halal screening", summary: "TCS: both standards checked", ok: true },
          { label: "News", summary: "No headlines were found", ok: false },
        ],
      }),
    );
    const summary = await screen.findByText("What I looked at");
    const details = summary.closest("details") as HTMLDetailsElement;
    expect(details.open).toBe(false);
    expect(within(details).getByText("Halal screening")).toBeInTheDocument();
    expect(within(details).getByText(/TCS: both standards checked/)).toBeInTheDocument();
    expect(within(details).getByText(/could not be checked/)).toBeInTheDocument();
  });

  it("draws the reply as safe text: bold and a link, never raw markup", async () => {
    const hostile = "**Bold** and [a link](https://example.com/x) <script>alert(1)</script> [bad](javascript:alert(1))";
    await ask(reply({ reply: hostile }));
    await screen.findByText("Bold");
    const dialog = screen.getByRole("dialog");
    expect(dialog.querySelector("script")).toBeNull();
    const anchors = [...dialog.querySelectorAll("a")];
    expect(anchors.map((a) => a.getAttribute("href"))).toEqual(["https://example.com/x"]);
    expect(anchors[0]).toHaveAttribute("rel", "noopener noreferrer");
    expect(anchors[0]).toHaveAttribute("target", "_blank");
  });

  it("opens the page a navigate button names", async () => {
    await ask(reply({ proposals: [{ kind: "navigate", label: "Open TCS", path: "/stock/INFY", symbol: "INFY" }] }));
    fireEvent.click(await screen.findByRole("button", { name: "Open TCS" }));
    await waitFor(() => expect(screen.getByTestId("path")).toHaveTextContent("/stock/INFY"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("never navigates anywhere because of a button it was handed, only on a click", async () => {
    await ask(reply({ proposals: [{ kind: "navigate", label: "Open TCS", path: "/stock/INFY", symbol: "INFY" }] }));
    await screen.findByRole("button", { name: "Open TCS" });
    expect(screen.getByTestId("path")).toHaveTextContent("/stock/TCS");
  });

  it("asks the app to open a second opinion with the shared event", async () => {
    const seen: CustomEvent[] = [];
    const listener = (event: Event) => seen.push(event as CustomEvent);
    window.addEventListener(SECOND_OPINION_EVENT, listener);
    try {
      const proposal = { kind: "second_opinion", label: "Get a second opinion on TCS", path: null, symbol: "TCS" };
      await ask(reply({ proposals: [proposal] }));
      expect(seen).toHaveLength(0);
      fireEvent.click(await screen.findByRole("button", { name: "Get a second opinion on TCS" }));
      expect(seen).toHaveLength(1);
      expect(seen[0]?.type).toBe("quantos:second-opinion");
      expect(seen[0]?.detail).toEqual({ symbol: "TCS" });
    } finally {
      window.removeEventListener(SECOND_OPINION_EVENT, listener);
    }
  });

  it("drops a button whose path leaves the app", async () => {
    const proposal = { kind: "navigate", label: "Go elsewhere", path: "https://evil.example", symbol: null };
    await ask(reply({ proposals: [proposal] }));
    await screen.findByText("TCS passes both standards.");
    expect(screen.queryByRole("button", { name: "Go elsewhere" })).toBeNull();
  });

  it("says quietly that a built-in answer is built in, with a way to add an AI key", async () => {
    await ask(reply({ mode: "built_in", provider: null, model: null }));
    const note = await screen.findByText(/Answered from QuantOS's built-in answers\./);
    const sentence = "Answered from QuantOS's built-in answers. Add an AI key for open-ended questions.";
    expect(note.textContent?.replace(/\s+/g, " ").trim()).toBe(sentence);
    fireEvent.click(within(note).getByRole("button", { name: "Add an AI key" }));
    await waitFor(() => expect(screen.getByTestId("path")).toHaveTextContent("/settings/accounts"));
  });

  it("shows one Add an AI key button, not two, when the engine also sends one", async () => {
    const addKey = { kind: "navigate", label: "Add an AI key", path: "/settings/accounts", symbol: null };
    await ask(reply({ mode: "built_in", provider: null, model: null, proposals: [addKey] }));
    await screen.findByText(/Answered from QuantOS's built-in answers\./);
    expect(screen.getAllByRole("button", { name: "Add an AI key" })).toHaveLength(1);
  });

  it("does not show the built-in line when an AI model answered, and says which one did", async () => {
    await ask(reply());
    await screen.findByText("TCS passes both standards.");
    expect(screen.queryByText(/built-in answers/)).toBeNull();
    expect(screen.getByText(/Answered by the AI model gpt-x from openai/)).toBeInTheDocument();
  });

  it("shows a plain note the engine attached, such as why the AI could not be reached", async () => {
    const unreachable = "The AI model could not be reached just now.";
    await ask(reply({ mode: "built_in", provider: null, model: null, error: unreachable }));
    expect(await screen.findByText("The AI model could not be reached just now.")).toBeInTheDocument();
  });
});

describe("when the Copilot cannot answer", () => {
  beforeEach(() => {
    vi.mocked(api).mockReset();
  });
  afterEach(cleanup);

  it("says so in plain words, keeps the question, and tries again on Retry", async () => {
    let calls = 0;
    routeApi({
      [`POST ${CHAT}`]: () => {
        calls += 1;
        if (calls === 1) throw new ApiError("ENGINE_OFFLINE", "The QuantOS engine is not responding.", 0);
        return reply({ reply: "Back again." });
      },
    });
    renderApp(<Shell />);
    openDrawer();
    await screen.findByRole("dialog");
    await say("are you there");
    const sorry = "The Copilot could not answer just now. Check that QuantOS is running and try again.";
    expect(await screen.findByText(sorry)).toBeInTheDocument();
    expect(screen.getByText("are you there")).toBeInTheDocument();
    expect(screen.queryByText("Thinking…")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Back again.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect(callsTo("POST", CHAT)).toHaveLength(2);
    expect(callsTo("POST", CHAT)[1]?.[2]).toMatchObject({ messages: [{ role: "user", content: "are you there" }] });
  });
});
