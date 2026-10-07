import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  AI_READY,
  card,
  daily,
  engine,
  mine,
  needsAi,
  ready,
  RESULT,
  runUrl,
  TOOLS,
} from "../components/agents/agentFixtures";
import { renderApp, routeApi } from "../components/agents/testHarness";
import type { Agent, RunResult } from "../lib/agents";
import { api, ApiError } from "../lib/api";
import Agents from "./Agents";

vi.mock("../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../lib/api")>();
  return { ...real, api: vi.fn() };
});

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

// -------------------------------------------------------------------------------- the list tells the truth

interface Shelf {
  agents: Agent[];
}

/** Keeps what was saved: the replaced agent, or a new one at the end. */
function keep(shelf: Shelf, saved: Agent): Agent {
  const known = shelf.agents.some((agent) => agent.id === saved.id);
  const replaced = shelf.agents.map((agent) => (agent.id === saved.id ? saved : agent));
  shelf.agents = known ? replaced : [...shelf.agents, saved];
  return saved;
}

/** The agent is removed, and the person is told it was already gone. */
function forgetThenRefuse(shelf: Shelf): never {
  shelf.agents = shelf.agents.filter((agent) => agent.id !== "mine1");
  throw new ApiError("NOT_FOUND", "That agent no longer exists.", 404, null);
}

/** An engine that remembers: what is saved or deleted is what the next request for the list returns. */
function keepingEngine(extra: Record<string, unknown> = {}) {
  const shelf: Shelf = { agents: [mine, daily] };
  routeApi({
    "GET /api/v2/copilot/tools": TOOLS,
    "GET /api/v2/copilot/models": AI_READY,
    "GET /api/v2/copilot/agents": () => ({ agents: shelf.agents, recipes: [ready, needsAi] }),
    "PUT /api/v2/copilot/agents/mine1": (body: unknown) => keep(shelf, { ...mine, ...(body as object) }),
    "POST /api/v2/copilot/agents": (body: unknown) => keep(shelf, { ...mine, id: "made1", ...(body as object) }),
    "DELETE /api/v2/copilot/agents/mine1": () => forgetThenRefuse(shelf),
    ...extra,
  });
}

describe("the list after a change", () => {
  it("shows the new description the moment it says Saved, not the old one", async () => {
    keepingEngine();
    renderApp(<Agents />);
    await screen.findByRole("heading", { name: "My halal check" });
    fireEvent.click(within(card("My halal check")).getByRole("button", { name: "Edit" }));
    await screen.findByRole("checkbox", { name: /Halal screening/ });
    fireEvent.change(screen.getByLabelText("What is it for?"), { target: { value: "Now checks everything." } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("Saved My halal check.");
    expect(within(card("My halal check")).getByText("Now checks everything.")).toBeInTheDocument();
    expect(within(card("My halal check")).queryByText("Checks a stock I am watching.")).toBeNull();
  });

  it("shows a new agent the moment it says Saved", async () => {
    keepingEngine();
    renderApp(<Agents />);
    await screen.findByRole("heading", { name: "My halal check" });
    fireEvent.click(screen.getByRole("button", { name: "New agent" }));
    await screen.findByRole("checkbox", { name: /Halal screening/ });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Brand new" } });
    fireEvent.click(screen.getByRole("checkbox", { name: /Price facts/ }));
    fireEvent.change(screen.getByLabelText("Step 1"), { target: { value: "Show the facts about {symbol}." } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("Saved Brand new.");
    expect(screen.getByRole("heading", { name: "Brand new" })).toBeInTheDocument();
  });

  it("takes an agent off the list when deleting finds it already gone, and still says so", async () => {
    keepingEngine();
    renderApp(<Agents />);
    await screen.findByRole("heading", { name: "My halal check" });
    fireEvent.click(within(card("My halal check")).getByRole("button", { name: "Delete" }));
    await screen.findByRole("dialog");
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(await screen.findByText("That agent no longer exists.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("heading", { name: "My halal check", hidden: true })).toBeNull());
    expect(screen.getByRole("heading", { name: "Daily look", hidden: true })).toBeInTheDocument();
  });

  it("takes the agent off the list at once on a refused delete even if the list cannot be asked again", async () => {
    let asked = 0;
    keepingEngine({
      "GET /api/v2/copilot/agents": () => {
        asked += 1;
        if (asked > 1) throw new Error("offline");
        return { agents: [mine, daily], recipes: [ready, needsAi] };
      },
    });
    renderApp(<Agents />);
    await screen.findByRole("heading", { name: "My halal check" });
    fireEvent.click(within(card("My halal check")).getByRole("button", { name: "Delete" }));
    await screen.findByRole("dialog");
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(await screen.findByText("That agent no longer exists.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "My halal check", hidden: true })).toBeNull();
  });
});

describe("what an agent's result says", () => {
  async function runResult(result: RunResult) {
    engine({ [`POST ${runUrl("mine1")}`]: result });
    renderApp(<Agents />);
    await screen.findByRole("heading", { name: "My halal check" });
    fireEvent.click(within(card("My halal check")).getByRole("button", { name: "Run" }));
    fireEvent.change(screen.getByLabelText("Which stock?"), { target: { value: "TCS" } });
    fireEvent.submit(screen.getByLabelText("Which stock?").closest("form") as HTMLFormElement);
  }

  it("writes dates the way a person reads them, and leaves web addresses alone", async () => {
    const step = {
      ...RESULT.steps[0],
      text: "Show the facts to 2021-03-23.",
      reply:
        "Data ends **2021-03-23** and 2021-02-31 is not a date. " +
        "See [the filing of 2021-03-24](https://example.com/2021-03-25).",
      looked_at: [{ label: "Price facts", summary: "Latest price is from 2021-03-23", ok: true }],
    } as RunResult["steps"][number];
    await runResult({ ...RESULT, steps: [step], note: "Data runs to 2021-03-23." });
    expect(await screen.findByText("Show the facts to 23 Mar 2021.")).toBeInTheDocument();
    expect(screen.getByText("23 Mar 2021", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText(/2021-02-31 is not a date/)).toBeInTheDocument();
    const filing = screen.getByRole("link", { name: "the filing of 24 Mar 2021" });
    expect(filing).toHaveAttribute("href", "https://example.com/2021-03-25");
    expect(screen.getByText("Latest price is from 23 Mar 2021")).toBeInTheDocument();
    expect(screen.getByText("Data runs to 23 Mar 2021.")).toBeInTheDocument();
  });

  it("says an AI model wrote it, never the model's own identifier", async () => {
    await runResult({ ...RESULT, model: "anthropic-model" });
    expect(await screen.findByText(/Written with an AI model\./)).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("anthropic-model");
  });
});
