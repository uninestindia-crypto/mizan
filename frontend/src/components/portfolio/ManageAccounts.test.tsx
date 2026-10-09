import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { callsTo } from "../agents/testHarness";
import { forgetHiddenChoices } from "../mode/hiddenChoice";
import { api } from "../../lib/api";
import { openManager, refuse, type } from "./managerKit";
import { ACCOUNT_LIST, engine } from "./portfolioKit";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

beforeEach(() => {
  vi.mocked(api).mockReset();
  forgetHiddenChoices();
  localStorage.clear();
});
afterEach(cleanup);

describe("the accounts window", () => {
  it("lists every account with whose it is, its kind, its broker and how many holdings it has", async () => {
    engine();
    const manager = await openManager();
    const list = within(manager.getByRole("list", { name: "Your accounts" }));
    expect(list.getAllByRole("listitem")).toHaveLength(3);
    expect(list.getByText("Asha · Demat account · Zerodha")).toBeInTheDocument();
    expect(list.getByText("2 holdings")).toBeInTheDocument();
    expect(list.getByText("No holdings yet")).toBeInTheDocument();
  });

  it("closes with Escape and gives focus back to the button that opened it", async () => {
    engine();
    await openManager();
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.getByRole("button", { name: "Manage accounts" })).toHaveFocus();
  });
});

describe("adding an account", () => {
  const ADDED = {
    id: 4,
    name: "Mummy's Groww",
    owner: "Mummy",
    kind: "Mutual fund account",
    broker: "Groww",
    holdings: 0,
  };

  it("sends the name, the owner, the kind and the broker, and says it is saved", async () => {
    engine({ "POST /api/v2/accounts": ADDED });
    const manager = await openManager();
    fireEvent.click(manager.getByRole("button", { name: "Add an account" }));
    type("Name", "Mummy's Groww");
    type("Whose account is it?", "Mummy");
    type("Kind of account", "Mutual fund account");
    type("Broker (optional)", "Groww");
    fireEvent.click(screen.getByRole("button", { name: "Add account" }));
    expect(await screen.findByText("Saved “Mummy's Groww”.")).toBeInTheDocument();
    expect(callsTo("POST", "/api/v2/accounts")).toEqual([
      { name: "Mummy's Groww", owner: "Mummy", kind: "Mutual fund account", broker: "Groww" },
    ]);
  });

  it("offers the fixed kinds, hints at the broker, and starts on the person's own Demat account", async () => {
    engine();
    const manager = await openManager();
    fireEvent.click(manager.getByRole("button", { name: "Add an account" }));
    const kinds = within(screen.getByLabelText("Kind of account")).getAllByRole("option");
    expect(kinds.map((k) => k.textContent)).toEqual(ACCOUNT_LIST.kinds);
    expect(screen.getByLabelText("Kind of account")).toHaveValue("Demat account");
    expect(screen.getByLabelText("Whose account is it?")).toHaveValue("Me");
    expect(screen.getByText(/For example Zerodha, Groww, Upstox or HDFC Securities/)).toBeInTheDocument();
  });

  it("needs a name before it can be saved, and puts the cursor in the name", async () => {
    engine();
    const manager = await openManager();
    fireEvent.click(manager.getByRole("button", { name: "Add an account" }));
    expect(screen.getByRole("button", { name: "Add account" })).toBeDisabled();
    expect(screen.getByLabelText("Name")).toHaveFocus();
  });

  it("shows the server's own sentence when the name is taken, and stays on the form", async () => {
    const taken = "You already have an account called “My account”. Choose another name.";
    engine({ "POST /api/v2/accounts": refuse("ACCOUNT_INVALID", taken) });
    const manager = await openManager();
    fireEvent.click(manager.getByRole("button", { name: "Add an account" }));
    type("Name", "My account");
    fireEvent.click(screen.getByRole("button", { name: "Add account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(taken);
    expect(screen.getByLabelText("Name")).toHaveValue("My account");
  });

  it("goes back to the button that opened the form when it is cancelled", async () => {
    engine();
    const manager = await openManager();
    fireEvent.click(manager.getByRole("button", { name: "Add an account" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(await screen.findByRole("button", { name: "Add an account" })).toHaveFocus();
  });
});

describe("changing an account", () => {
  it("starts from what is saved and sends the change", async () => {
    engine({ "PUT /api/v2/accounts/2": { ...ACCOUNT_LIST.accounts[1], name: "Asha long-term" } });
    const manager = await openManager();
    fireEvent.click(manager.getByRole("button", { name: "Edit Asha's Zerodha" }));
    expect(screen.getByLabelText("Name")).toHaveValue("Asha's Zerodha");
    expect(screen.getByLabelText("Broker (optional)")).toHaveValue("Zerodha");
    type("Name", "Asha long-term");
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("Saved “Asha long-term”.")).toBeInTheDocument();
    expect(callsTo("PUT", "/api/v2/accounts/2")).toEqual([
      { name: "Asha long-term", owner: "Asha", kind: "Demat account", broker: "Zerodha" },
    ]);
  });

  it("gives focus back to the Edit button when the change is cancelled", async () => {
    engine();
    const manager = await openManager();
    fireEvent.click(manager.getByRole("button", { name: "Edit Asha's Zerodha" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(await screen.findByRole("button", { name: "Edit Asha's Zerodha" })).toHaveFocus();
  });
});
