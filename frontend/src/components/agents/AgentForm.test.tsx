import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { type Agent, copyTarget, editTarget, newTarget } from "../../lib/agents";
import { api, ApiError } from "../../lib/api";
import { AgentForm } from "./AgentForm";
import { callsTo, renderApp, routeApi } from "./testHarness";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

const TOOLS = {
  tools: [
    { name: "stock_facts", label: "Price facts", help: "Prices and returns.", description: "For the model: prices." },
    {
      name: "shariah_check",
      label: "Halal screening",
      help: "Checks both standards.",
      description: "For the model: only this tool may state a halal verdict.",
    },
  ],
};
const saved: Agent = {
  id: "a1",
  name: "My check",
  description: "",
  instructions: "",
  tools: ["stock_facts"],
  steps: ["Show the facts about {symbol}."],
  needs_symbol: true,
  built_in: false,
};

const rejected = (problems: { field: string; message: string }[]) => () => {
  throw new ApiError("AGENT_INVALID", "Check the highlighted fields.", 422, { problems });
};

function open(target = newTarget(), table: Record<string, unknown> = {}) {
  const onClose = vi.fn();
  routeApi({ "GET /api/v2/copilot/tools": TOOLS, ...table });
  renderApp(<AgentForm target={target} onClose={onClose} />);
  return onClose;
}

const type = (label: string | RegExp, value: string) => {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
};

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

describe("the agent form", () => {
  it("asks in plain words and shows what it may look at by label, never by the name it is saved under", async () => {
    open();
    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.getByLabelText("What is it for?")).toBeInTheDocument();
    expect(screen.getByLabelText("How should it behave?")).toBeInTheDocument();
    expect(screen.getByText("Optional. For example: keep answers short")).toBeInTheDocument();
    expect(await screen.findByRole("checkbox", { name: /Price facts/ })).toBeInTheDocument();
    expect(screen.getByText("Checks both standards.")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("only this tool may state");
    expect(document.body.textContent).not.toContain("stock_facts");
    expect(document.body.textContent).not.toContain("shariah_check");
  });

  it("explains how to write steps", () => {
    open();
    const help = "Write each step as a request, in your own words. Use {symbol} where the stock's name should go.";
    expect(screen.getByText(help)).toBeInTheDocument();
  });

  it("opens an agent filled in, and a copy with a new name", async () => {
    open(editTarget({ ...saved, name: "Mine" }));
    expect(screen.getByLabelText("Name")).toHaveValue("Mine");
    expect(screen.getByLabelText("Step 1")).toHaveValue("Show the facts about {symbol}.");
    expect(await screen.findByRole("checkbox", { name: /Price facts/ })).toBeChecked();
    cleanup();
    open(copyTarget({ ...saved, name: "Ready one", built_in: true }));
    expect(screen.getByLabelText("Name")).toHaveValue("My copy of Ready one");
  });
});

describe("writing the steps", () => {
  it("adds, reorders and removes steps", () => {
    open();
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    type("Step 1", "first");
    type("Step 2", "second");
    fireEvent.click(screen.getByRole("button", { name: "Move step 2 up" }));
    expect(screen.getByLabelText("Step 1")).toHaveValue("second");
    expect(screen.getByLabelText("Step 2")).toHaveValue("first");
    expect(screen.getByRole("button", { name: "Move step 1 up" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Move step 2 down" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Remove step 1" }));
    expect(screen.queryByLabelText("Step 2")).toBeNull();
    expect(screen.getByLabelText("Step 1")).toHaveValue("first");
  });

  it("stops offering Add step at the most steps", () => {
    open();
    for (let i = 0; i < 7; i++) fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    expect(screen.getAllByLabelText(/^Step \d$/)).toHaveLength(8);
    expect(screen.getByRole("button", { name: "Add step" })).toBeDisabled();
  });

  it("says when a step will ask for the stock", () => {
    open();
    expect(screen.queryByText("When you run this agent, it will ask which stock to use.")).toBeNull();
    type("Step 1", "Look at {symbol}");
    expect(screen.getByText("When you run this agent, it will ask which stock to use.")).toBeInTheDocument();
  });
});

describe("saving", () => {
  it("catches the obvious mistakes before sending anything, under the right field", async () => {
    open();
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Check the highlighted fields.")).toBeInTheDocument();
    expect(screen.getByText("Give your agent a name.")).toBeInTheDocument();
    expect(screen.getByText("Tick at least one thing this agent may look at.")).toBeInTheDocument();
    expect(screen.getByText(/^Step 1 is empty/)).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Step 1")).toHaveAttribute("aria-invalid", "true");
    expect(callsTo("POST", "/api/v2/copilot/agents")).toHaveLength(0);
  });

  it("sends a new agent as a create, trimmed, and tells the screen it was saved", async () => {
    const onClose = open(newTarget(), { "POST /api/v2/copilot/agents": saved });
    type("Name", "  My check ");
    fireEvent.click(await screen.findByRole("checkbox", { name: /Price facts/ }));
    type("Step 1", " Show the facts about {symbol}. ");
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onClose).toHaveBeenCalledWith(saved));
    expect(callsTo("POST", "/api/v2/copilot/agents")).toEqual([
      {
        name: "My check",
        description: "",
        instructions: "",
        tools: ["stock_facts"],
        steps: ["Show the facts about {symbol}."],
      },
    ]);
  });

  it("sends a change to an agent as an update, and a copy of a ready-made one as a create", async () => {
    const edit = open(editTarget(saved), { "PUT /api/v2/copilot/agents/a1": saved });
    await screen.findByRole("checkbox", { name: /Price facts/ });
    type("Name", "Renamed");
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(edit).toHaveBeenCalled());
    expect(callsTo("PUT", "/api/v2/copilot/agents/a1")).toHaveLength(1);
    cleanup();
    const ready = copyTarget({ ...saved, id: "recipe_halal", built_in: true });
    const copy = open(ready, { "POST /api/v2/copilot/agents": saved });
    await screen.findByRole("checkbox", { name: /Price facts/ });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(copy).toHaveBeenCalled());
    expect(callsTo("PUT", "/api/v2/copilot/agents/recipe_halal")).toHaveLength(0);
  });
});

describe("problems the engine finds", () => {
  const problems = [
    { field: "name", message: "You already have an agent with that name. Choose another." },
    { field: "steps", message: "Step 1 uses {price}. The only fill-in you can use is {symbol}." },
  ];

  it("shows each message exactly as written under its own field, with the summary line", async () => {
    const onClose = open(editTarget(saved), { "PUT /api/v2/copilot/agents/a1": rejected(problems) });
    await screen.findByRole("checkbox", { name: /Price facts/ });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    const summary = await screen.findByText("Check the highlighted fields.");
    expect(summary).toBeInTheDocument();
    const nameField = screen.getByLabelText("Name").parentElement as HTMLElement;
    expect(within(nameField).getByText(problems[0]?.message as string)).toBeInTheDocument();
    expect(screen.getByText(problems[1]?.message as string)).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("clears a field's message as soon as the person changes that field", async () => {
    open(editTarget(saved), { "PUT /api/v2/copilot/agents/a1": rejected(problems) });
    await screen.findByRole("checkbox", { name: /Price facts/ });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText(problems[0]?.message as string);
    type("Name", "Another name");
    expect(screen.queryByText(problems[0]?.message as string)).toBeNull();
    expect(screen.getByText(problems[1]?.message as string)).toBeInTheDocument();
  });

  it("says plainly when the engine could not be reached", async () => {
    const offline = () => {
      throw new ApiError("ENGINE_OFFLINE", "The QuantOS engine is not responding.", 0);
    };
    open(editTarget(saved), { "PUT /api/v2/copilot/agents/a1": offline });
    await screen.findByRole("checkbox", { name: /Price facts/ });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("The QuantOS engine is not responding.")).toBeInTheDocument();
  });
});

describe("leaving the form", () => {
  it("closes at once when nothing was changed", () => {
    const onClose = open();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalledWith(null);
  });

  it("asks first, in the app, when something was changed", async () => {
    const confirm = vi.spyOn(window, "confirm");
    const onClose = open();
    type("Name", "Half written");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(await screen.findByRole("dialog", { name: "Leave without saving?" })).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Keep editing" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.getByLabelText("Name")).toHaveValue("Half written");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    fireEvent.click(await screen.findByRole("button", { name: "Discard changes" }));
    expect(onClose).toHaveBeenCalledWith(null);
    expect(confirm).not.toHaveBeenCalled();
    confirm.mockRestore();
  });
});
