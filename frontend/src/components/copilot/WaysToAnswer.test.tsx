import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AiStatus } from "../../lib/aiSource";
import { api } from "../../lib/api";
import { CHAT, openDrawer, reply, say, Shell } from "./chatTestKit";
import { callsTo, renderApp, routeApi } from "./testHarness";

vi.mock("../../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../lib/api")>();
  return { ...original, api: vi.fn() };
});

const STATUS = "/api/v2/copilot/status";
const SETTINGS = "/api/v2/settings";
const OPENAI_MODELS = "/api/v2/ai/models/openai";
const entry = (id: string, model: string | null = null, thinking: string | null = null) => ({ id, model, thinking });

const READY: AiStatus = {
  ai_ready: true,
  apps: [],
  ai: { source: "cli", cli: null, api: null, fallback: true },
  providers: [
    { id: "anthropic", label: "Anthropic (Claude)", ready: false },
    { id: "openai", label: "OpenAI", ready: true },
    { id: "groq", label: "Groq", ready: true },
  ],
  defaults: { speed: "balanced", helpers: 1 },
};

const OPENAI_FOUND = { provider: "openai", total: 2, newest: [{ id: "gpt-9", name: "gpt-9", created: 1 }] };

function engine(over: Record<string, (body: unknown) => unknown> = {}) {
  routeApi({
    [`POST ${CHAT}`]: () => reply(),
    [`GET ${STATUS}`]: () => structuredClone(READY),
    [`GET ${OPENAI_MODELS}`]: () => OPENAI_FOUND,
    [`PUT ${SETTINGS}`]: (body: unknown) => {
      const sent = body as { ai_order?: unknown; ai_defaults?: unknown };
      return { ai_order: sent.ai_order ?? [], ai_defaults: sent.ai_defaults };
    },
    ...over,
  });
}

const toggle = () => screen.getByRole("button", { name: /Ways to answer/ });
const bodies = (method: string, path: string) => callsTo(method, path).map((call) => call[2]);
const asked = () => bodies("POST", CHAT) as { prefs?: unknown }[];

async function opened() {
  renderApp(<Shell />);
  openDrawer();
  await screen.findByRole("dialog");
  fireEvent.click(toggle());
  await screen.findByRole("combobox", { name: "Which AI" });
}

beforeEach(() => {
  vi.mocked(api).mockReset();
  window.localStorage.clear();
});
afterEach(cleanup);

describe("ways to answer", () => {
  it("is closed, asks the engine nothing, and a message goes out with no choices", async () => {
    engine();
    renderApp(<Shell />);
    openDrawer();
    await screen.findByRole("dialog");
    expect(toggle()).toHaveAttribute("aria-expanded", "false");
    expect(callsTo("GET", STATUS)).toHaveLength(0);
    await say("Is TCS halal?");
    await waitFor(() => expect(asked()).toHaveLength(1));
    expect(asked()[0]).not.toHaveProperty("prefs");
  });

  it("lists the AIs that are ready, starts on the usual order and Balanced, and says nothing is changed", async () => {
    engine();
    await opened();
    const which = screen.getByRole("combobox", { name: "Which AI" });
    expect(which).toHaveValue("");
    expect(within(which).getAllByRole("option").map((o) => o.textContent)).toEqual(["My usual order", "OpenAI", "Groq"]);
    expect(screen.getByRole("radio", { name: "Balanced" })).toBeChecked();
    expect(screen.queryByText("Changed")).toBeNull();
    expect(screen.getByText("Pick an AI to choose its model and how hard it thinks.")).toBeInTheDocument();
  });

  it("sends a different speed with the next message and says the way of answering is changed", async () => {
    engine();
    await opened();
    fireEvent.click(screen.getByRole("radio", { name: "Careful" }));
    expect(screen.getByText("Changed")).toBeInTheDocument();
    await say("Is TCS halal?");
    await waitFor(() => expect(asked()).toHaveLength(1));
    expect(asked()[0]?.prefs).toEqual({ speed: "careful" });
  });

  it("sends the AI, model and thinking level that were picked", async () => {
    engine();
    await opened();
    fireEvent.change(screen.getByRole("combobox", { name: "Which AI" }), { target: { value: "openai" } });
    await screen.findByRole("option", { name: "gpt-9" });
    fireEvent.change(screen.getByRole("combobox", { name: /^Model/ }), { target: { value: "gpt-9" } });
    const levels = screen.getByRole("combobox", { name: /How hard it thinks/ });
    await waitFor(() => expect(within(levels).getAllByRole("option").length).toBeGreaterThan(1));
    fireEvent.change(levels, { target: { value: "high" } });
    await say("Is TCS halal?");
    await waitFor(() => expect(asked()).toHaveLength(1));
    expect(asked()[0]?.prefs).toEqual({ ai: "openai", model: "gpt-9", thinking: "high" });
  });

  it("starts the model and level over when another AI is picked", async () => {
    engine({ "GET /api/v2/ai/models/groq": () => ({ provider: "groq", total: 0, newest: [] }) });
    await opened();
    fireEvent.change(screen.getByRole("combobox", { name: "Which AI" }), { target: { value: "openai" } });
    await screen.findByRole("option", { name: "gpt-9" });
    fireEvent.change(screen.getByRole("combobox", { name: /^Model/ }), { target: { value: "gpt-9" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Which AI" }), { target: { value: "groq" } });
    await say("hello");
    await waitFor(() => expect(asked()).toHaveLength(1));
    expect(asked()[0]?.prefs).toEqual({ ai: "groq" });
  });

  it("goes back to the usual way with one press", async () => {
    engine();
    await opened();
    fireEvent.click(screen.getByRole("radio", { name: "Quick" }));
    fireEvent.click(screen.getByRole("button", { name: "Back to my usual" }));
    expect(screen.queryByText("Changed")).toBeNull();
    expect(screen.getByRole("radio", { name: "Balanced" })).toBeChecked();
    await say("hello");
    await waitFor(() => expect(asked()).toHaveLength(1));
    expect(asked()[0]).not.toHaveProperty("prefs");
  });

  it("makes the choice the usual way: that AI first with its choices, and the speed", async () => {
    engine();
    await opened();
    fireEvent.change(screen.getByRole("combobox", { name: "Which AI" }), { target: { value: "groq" } });
    fireEvent.click(screen.getByRole("radio", { name: "Quick" }));
    fireEvent.click(screen.getByRole("button", { name: "Make this my usual" }));
    await waitFor(() =>
      expect(bodies("PUT", SETTINGS)).toEqual([
        { ai_defaults: { speed: "quick" }, ai_order: [entry("groq"), entry("openai")] },
      ]),
    );
    expect(await screen.findByText("Saved")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Changed")).toBeNull());
  });

  it("says plainly when it cannot read which AIs are ready", async () => {
    engine({
      [`GET ${STATUS}`]: () => {
        throw new Error("offline");
      },
    });
    renderApp(<Shell />);
    openDrawer();
    await screen.findByRole("dialog");
    fireEvent.click(toggle());
    expect(await screen.findByText("QuantOS could not check which AI is ready.")).toBeInTheDocument();
  });

  it("uses no developer word", async () => {
    engine();
    await opened();
    expect(document.body.textContent).not.toMatch(/\b(API|token|terminal|command|CLI|JSON)\b/i);
  });
});
