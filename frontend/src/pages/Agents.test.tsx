import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { callsTo, deferred, newClient, renderApp, routeApi } from "../components/agents/testHarness";
import type { Agent, Recipe, RunResult } from "../lib/agents";
import { api } from "../lib/api";
import Agents from "./Agents";

vi.mock("../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../lib/api")>();
  return { ...real, api: vi.fn() };
});

const mine: Agent = {
  id: "mine1",
  name: "My halal check",
  description: "Checks a stock I am watching.",
  instructions: "",
  tools: ["shariah_check"],
  steps: ["Is {symbol} halal?", "Show the facts about {symbol}."],
  needs_symbol: true,
  built_in: false,
  created_at: "2026-10-06T10:00:00+00:00",
  updated_at: "2026-10-06T10:00:00+00:00",
};
const daily: Agent = { ...mine, id: "mine2", name: "Daily look", steps: ["Show my watchlist."], needs_symbol: false };
const ready: Recipe = {
  id: "recipe_check",
  name: "Check a stock, step by step",
  description: "Facts, halal screen and news for one stock.",
  instructions: "",
  tools: ["stock_facts", "shariah_check"],
  steps: ["Show the facts about {symbol}."],
  needs_symbol: true,
  built_in: true,
  needs_ai: false,
};
const needsAi: Recipe = { ...ready, id: "recipe_news", name: "Read the news", needs_ai: true };

const TOOLS = {
  tools: [
    { name: "stock_facts", label: "Price facts", help: "Prices.", description: "For the model: prices." },
    { name: "shariah_check", label: "Halal screening", help: "Both standards.", description: "For the model." },
  ],
};

const RESULT: RunResult = {
  name: "Check a stock, step by step",
  symbol: "TCS",
  steps: [
    {
      number: 1,
      text: "Show the facts about TCS.",
      reply: "TCS has been **steady**.\n\n- one\n- see [the filing](https://example.com/f)",
      looked_at: [
        { label: "Price facts", summary: "One-year return 12%", ok: true },
        { label: "News", summary: "Could not reach the news.", ok: false },
      ],
      error: null,
    },
    { number: 2, text: "Is TCS halal?", reply: "", looked_at: [], error: "That step could not finish." },
  ],
  proposals: [
    { kind: "navigate", label: "Open TCS", path: "/stock/TCS", symbol: "TCS" },
    { kind: "second_opinion", label: "Get a second opinion on TCS", path: null, symbol: "TCS" },
    { kind: "navigate", label: "Somewhere else", path: "https://evil.example", symbol: null },
  ],
  model: null,
  completed: true,
  note: "No AI key was used, so each step used the built-in answers.",
};

function engine(extra: Record<string, unknown> = {}, agents: Agent[] = [mine, daily]) {
  routeApi({
    "GET /api/v2/copilot/tools": TOOLS,
    "GET /api/v2/copilot/agents": { agents, recipes: [ready, needsAi] },
    ...extra,
  });
}

const runUrl = (id: string) => `/api/v2/copilot/agents/${id}/run`;
const card = (name: string) => screen.getByRole("heading", { name }).closest("article") as HTMLElement;

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

describe("the Agents screen", () => {
  it("says what agents are and that none can place an order", async () => {
    engine();
    renderApp(<Agents />);
    const purpose =
      "Agents are assistants you set up once and run whenever you like. Each one follows the steps you write, " +
      "and can only look at the things you tick. No agent can place an order.";
    expect(await screen.findByText(purpose)).toBeInTheDocument();
  });

  it("lists my agents and the ready-made ones in two sections, with what each may look at in plain words", async () => {
    engine();
    renderApp(<Agents />);
    expect(await screen.findByRole("heading", { name: "My agents" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Ready-made" })).toBeInTheDocument();
    expect(within(card("My halal check")).getByText(/Looks at: Halal screening/)).toBeInTheDocument();
    expect(within(card("My halal check")).getByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(within(card("My halal check")).getByRole("button", { name: "Delete" })).toBeInTheDocument();
    const premade = within(card("Check a stock, step by step"));
    expect(premade.getByRole("button", { name: "Copy and edit" })).toBeInTheDocument();
    expect(within(card("Check a stock, step by step")).queryByRole("button", { name: "Delete" })).toBeNull();
    expect(document.body.textContent).not.toMatch(/stock_facts|shariah_check/);
  });

  it("tells a person with no agents what to do next", async () => {
    engine({}, []);
    renderApp(<Agents />);
    expect(await screen.findByText("You have no agents yet")).toBeInTheDocument();
    const next = "Pick a ready-made agent and choose Copy and edit, or choose New agent.";
    expect(screen.getByText(next)).toBeInTheDocument();
  });

  it("notes that an agent works best with an AI key, and still lets it be run", async () => {
    engine();
    renderApp(<Agents />);
    const news = await screen.findByRole("heading", { name: "Read the news" });
    const note = within(news.closest("article") as HTMLElement);
    expect(note.getByText("Works best with an AI key")).toBeInTheDocument();
    expect(note.getByRole("link", { name: "Add a key" })).toHaveAttribute("href", "/settings/accounts");
    expect(note.getByRole("button", { name: "Run" })).toBeEnabled();
    expect(within(card("Check a stock, step by step")).queryByText("Works best with an AI key")).toBeNull();
  });

  it("says plainly, with a way to retry, when the agents cannot be loaded", async () => {
    routeApi({ "GET /api/v2/copilot/tools": TOOLS });
    renderApp(<Agents />);
    expect(await screen.findByText("Your agents could not be loaded")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});

describe("running an agent that needs a stock", () => {
  async function openRun(client = newClient()) {
    const view = renderApp(<Agents />, client);
    await screen.findByRole("heading", { name: "My halal check" });
    fireEvent.click(within(card("My halal check")).getByRole("button", { name: "Run" }));
    return view;
  }

  it("asks which stock, in upper case, and will not run without a real symbol", async () => {
    engine();
    await openRun();
    const box = screen.getByLabelText("Which stock?");
    fireEvent.change(box, { target: { value: "tcs" } });
    expect(box).toHaveValue("TCS");
    fireEvent.change(box, { target: { value: "T!CS" } });
    fireEvent.submit(box.closest("form") as HTMLFormElement);
    expect(await screen.findByText("Use letters and numbers only, for example TCS or M&M.")).toBeInTheDocument();
    expect(callsTo("POST", runUrl("mine1"))).toHaveLength(0);
  });

  it("shows progress while it runs, keeps the screen usable, then shows the steps", async () => {
    const pending = deferred<RunResult>();
    engine({ [`POST ${runUrl("mine1")}`]: () => pending.promise });
    await openRun();
    fireEvent.change(screen.getByLabelText("Which stock?"), { target: { value: "tcs" } });
    fireEvent.submit(screen.getByLabelText("Which stock?").closest("form") as HTMLFormElement);
    expect(await screen.findByText("Running step by step... this can take a minute")).toBeInTheDocument();
    expect(callsTo("POST", runUrl("mine1"))).toEqual([{ symbol: "TCS" }]);
    expect(screen.getByRole("button", { name: "New agent" })).toBeEnabled();
    await act(async () => pending.resolve(RESULT));
    expect(await screen.findByText("Show the facts about TCS.")).toBeInTheDocument();
    expect(screen.queryByText("Running step by step... this can take a minute")).toBeNull();
  });

  it("shows each step's words, what it looked at (collapsed, failures marked), errors and the note", async () => {
    engine({ [`POST ${runUrl("mine1")}`]: RESULT });
    await openRun();
    fireEvent.change(screen.getByLabelText("Which stock?"), { target: { value: "TCS" } });
    fireEvent.submit(screen.getByLabelText("Which stock?").closest("form") as HTMLFormElement);
    expect(await screen.findByText("steady")).toBeInTheDocument();
    expect(screen.getByText("steady").tagName).toBe("STRONG");
    expect(screen.getAllByRole("listitem").some((li) => li.textContent?.includes("one"))).toBe(true);
    const details = screen.getByText("What it looked at (2)").closest("details") as HTMLDetailsElement;
    expect(details.open).toBe(false);
    expect(within(details).getByText("Could not be looked up")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("That step could not finish.");
    expect(screen.getByText("No AI key was used, so each step used the built-in answers.")).toBeInTheDocument();
    expect(screen.getByText(/It is not advice\./)).toBeInTheDocument();
  });

  it("offers each proposal as a button the person clicks, and only the safe ones", async () => {
    engine({ [`POST ${runUrl("mine1")}`]: RESULT });
    await openRun();
    fireEvent.change(screen.getByLabelText("Which stock?"), { target: { value: "TCS" } });
    fireEvent.submit(screen.getByLabelText("Which stock?").closest("form") as HTMLFormElement);
    const open = await screen.findByRole("button", { name: "Open TCS" });
    expect(screen.queryByRole("button", { name: "Somewhere else" })).toBeNull();
    const heard = vi.fn();
    window.addEventListener("quantos:second-opinion", heard);
    fireEvent.click(screen.getByRole("button", { name: "Get a second opinion on TCS" }));
    expect((heard.mock.calls[0]?.[0] as CustomEvent).detail).toEqual({ symbol: "TCS" });
    window.removeEventListener("quantos:second-opinion", heard);
    fireEvent.click(open);
    expect(screen.getByTestId("where")).toHaveTextContent("/stock/TCS");
  });

  it("shows the engine's plain note when it could not run at all", async () => {
    const refused: RunResult = { ...RESULT, steps: [], completed: false, proposals: [], note: "Tell me which stock." };
    engine({ [`POST ${runUrl("mine1")}`]: refused });
    await openRun();
    fireEvent.change(screen.getByLabelText("Which stock?"), { target: { value: "TCS" } });
    fireEvent.submit(screen.getByLabelText("Which stock?").closest("form") as HTMLFormElement);
    expect(await screen.findByText("Tell me which stock.")).toBeInTheDocument();
    expect(screen.queryByText("The agent stopped before its last step.")).toBeNull();
  });

  it("shows a failed request in plain words, not as a crash", async () => {
    engine({ [`POST ${runUrl("mine1")}`]: () => { throw new Error("Something went wrong on the way."); } });
    await openRun();
    fireEvent.change(screen.getByLabelText("Which stock?"), { target: { value: "TCS" } });
    fireEvent.submit(screen.getByLabelText("Which stock?").closest("form") as HTMLFormElement);
    expect(await screen.findByText("Something went wrong on the way.")).toBeInTheDocument();
  });
});

describe("running an agent that needs no stock", () => {
  it("starts as soon as it is opened, without asking for a stock", async () => {
    engine({ [`POST ${runUrl("mine2")}`]: { ...RESULT, symbol: null, steps: [RESULT.steps[0]] } });
    renderApp(<Agents />);
    await screen.findByRole("heading", { name: "Daily look" });
    fireEvent.click(within(card("Daily look")).getByRole("button", { name: "Run" }));
    expect(await screen.findByText("Show the facts about TCS.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Which stock?")).toBeNull();
    expect(callsTo("POST", runUrl("mine2"))).toEqual([{}]);
  });
});

describe("leaving the screen while an agent runs", () => {
  it("keeps the answer, so coming back finds it", async () => {
    const pending = deferred<RunResult>();
    engine({ [`POST ${runUrl("mine2")}`]: () => pending.promise });
    const client = newClient();
    const first = renderApp(<Agents />, client);
    await screen.findByRole("heading", { name: "Daily look" });
    fireEvent.click(within(card("Daily look")).getByRole("button", { name: "Run" }));
    await screen.findByText("Running step by step... this can take a minute");
    first.unmount();
    await act(async () => pending.resolve({ ...RESULT, symbol: null }));
    renderApp(<Agents />, client);
    await screen.findByRole("heading", { name: "Daily look" });
    fireEvent.click(within(card("Daily look")).getByRole("button", { name: "Run" }));
    expect(await screen.findByText("Show the facts about TCS.")).toBeInTheDocument();
    expect(callsTo("POST", runUrl("mine2"))).toHaveLength(1);
  });

  it("shows that it is still running when the person comes back early", async () => {
    const pending = deferred<RunResult>();
    engine({ [`POST ${runUrl("mine2")}`]: () => pending.promise });
    const client = newClient();
    const first = renderApp(<Agents />, client);
    await screen.findByRole("heading", { name: "Daily look" });
    fireEvent.click(within(card("Daily look")).getByRole("button", { name: "Run" }));
    await screen.findByText("Running step by step... this can take a minute");
    first.unmount();
    renderApp(<Agents />, client);
    await screen.findByRole("heading", { name: "Daily look" });
    fireEvent.click(within(card("Daily look")).getByRole("button", { name: "Run" }));
    expect(await screen.findByText("Running step by step... this can take a minute")).toBeInTheDocument();
    expect(callsTo("POST", runUrl("mine2"))).toHaveLength(1);
    await act(async () => pending.resolve({ ...RESULT, symbol: null }));
  });
});

describe("making and changing agents", () => {
  it("opens a ready-made agent as the person's own copy, and saves it as a new agent", async () => {
    const created = { ...mine, id: "new1", name: "My copy of Check a stock, step by step" };
    engine({ "POST /api/v2/copilot/agents": created });
    renderApp(<Agents />);
    await screen.findByRole("heading", { name: "Check a stock, step by step" });
    fireEvent.click(within(card("Check a stock, step by step")).getByRole("button", { name: "Copy and edit" }));
    expect(screen.getByLabelText("Name")).toHaveValue("My copy of Check a stock, step by step");
    expect(await screen.findByRole("checkbox", { name: /Price facts/ })).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Saved My copy of Check a stock, step by step.")).toBeInTheDocument();
    expect(callsTo("POST", "/api/v2/copilot/agents")).toHaveLength(1);
    expect(callsTo("PUT", "/api/v2/copilot/agents/recipe_check")).toHaveLength(0);
  });

  it("edits one of mine and comes back to the list", async () => {
    engine({ "PUT /api/v2/copilot/agents/mine1": { ...mine, name: "Renamed" } });
    renderApp(<Agents />);
    await screen.findByRole("heading", { name: "My halal check" });
    fireEvent.click(within(card("My halal check")).getByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Renamed" } });
    await screen.findByRole("checkbox", { name: /Halal screening/ });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Saved Renamed.")).toBeInTheDocument();
  });
});

describe("deleting an agent", () => {
  async function askToDelete() {
    engine({ "DELETE /api/v2/copilot/agents/mine1": { deleted: true } });
    renderApp(<Agents />);
    await screen.findByRole("heading", { name: "My halal check" });
    fireEvent.click(within(card("My halal check")).getByRole("button", { name: "Delete" }));
    return screen.findByRole("dialog", { name: "Delete My halal check?" });
  }

  it("asks first, in the app and never with the browser's own pop-up, and can be called off", async () => {
    const confirm = vi.spyOn(window, "confirm");
    await askToDelete();
    fireEvent.click(screen.getByRole("button", { name: "Keep it" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(callsTo("DELETE", "/api/v2/copilot/agents/mine1")).toHaveLength(0);
    expect(confirm).not.toHaveBeenCalled();
    confirm.mockRestore();
  });

  it("deletes only once the person says so", async () => {
    await askToDelete();
    expect(callsTo("DELETE", "/api/v2/copilot/agents/mine1")).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(callsTo("DELETE", "/api/v2/copilot/agents/mine1")).toHaveLength(1));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});
