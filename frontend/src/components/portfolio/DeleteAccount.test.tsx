import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { forgetHiddenChoices } from "../mode/hiddenChoice";
import { api } from "../../lib/api";
import { openManager, refuse } from "./managerKit";
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

const LAST = "You need at least one account, so this one cannot be deleted.";
const HAS_HOLDINGS = "This account still holds 2 stocks. Choose where to move them first.";
function asked(path: string) {
  return vi.mocked(api).mock.calls.filter(([p, m]) => p === path && m === "DELETE");
}

describe("deleting an account with nothing in it", () => {
  it("says nothing is held, offers no place to move to, and deletes it", async () => {
    engine({ "DELETE /api/v2/accounts/3": { deleted: true, moved: 0 } });
    const manager = await openManager();
    fireEvent.click(manager.getByRole("button", { name: "Delete Papa's HUF" }));
    expect(await screen.findByText("Nothing is held in Papa's HUF. Nothing is sold.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Move holdings to")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Delete account" }));
    expect(await screen.findByText("Deleted “Papa's HUF”.")).toBeInTheDocument();
    expect(asked("/api/v2/accounts/3")).toHaveLength(1);
  });

  it("can be called off, and focus goes back to the Delete button", async () => {
    engine();
    const manager = await openManager();
    fireEvent.click(manager.getByRole("button", { name: "Delete Papa's HUF" }));
    fireEvent.click(await screen.findByRole("button", { name: "Keep it" }));
    expect(await screen.findByRole("button", { name: "Delete Papa's HUF" })).toHaveFocus();
    expect(asked("/api/v2/accounts/3")).toHaveLength(0);
  });
});

describe("deleting an account that holds stocks", () => {
  it("asks where the holdings go first, then moves them and deletes", async () => {
    engine({ "DELETE /api/v2/accounts/2?move_to=3": { deleted: true, moved: 2 } });
    const manager = await openManager();
    fireEvent.click(manager.getByRole("button", { name: "Delete Asha's Zerodha" }));
    const choice = await screen.findByLabelText("Move holdings to");
    const places = within(choice).getAllByRole("option").map((o) => o.textContent);
    expect(places).toEqual(["My account (Me)", "Papa's HUF (Papa)"]);
    fireEvent.change(choice, { target: { value: "3" } });
    expect(screen.getByText("2 holdings move to Papa's HUF.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete account" }));
    expect(await screen.findByText("Deleted “Asha's Zerodha”. 2 holdings moved to Papa's HUF.")).toBeInTheDocument();
    expect(asked("/api/v2/accounts/2?move_to=3")).toHaveLength(1);
  });

  it("moves them to the first other account when nothing else is chosen", async () => {
    engine({ "DELETE /api/v2/accounts/2?move_to=1": { deleted: true, moved: 2 } });
    const manager = await openManager();
    fireEvent.click(manager.getByRole("button", { name: "Delete Asha's Zerodha" }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete account" }));
    expect(await screen.findByText(/2 holdings moved to My account/)).toBeInTheDocument();
  });

  it("offers the choice with the server's sentence when the server says holdings are still there", async () => {
    const answers = { "DELETE /api/v2/accounts/3": refuse("ACCOUNT_HAS_HOLDINGS", HAS_HOLDINGS) };
    engine({ ...answers, "DELETE /api/v2/accounts/3?move_to=1": { deleted: true, moved: 2 } });
    const manager = await openManager();
    fireEvent.click(manager.getByRole("button", { name: "Delete Papa's HUF" }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(HAS_HOLDINGS);
    fireEvent.click(await screen.findByRole("button", { name: "Delete account" }));
    await waitFor(() => expect(asked("/api/v2/accounts/3?move_to=1")).toHaveLength(1));
  });
});

describe("the last account", () => {
  it("has no Delete button, and says why", async () => {
    const lonely = { accounts: [ACCOUNT_LIST.accounts[0]], kinds: ACCOUNT_LIST.kinds };
    engine({ "GET /api/v2/accounts": lonely });
    const manager = await openManager();
    expect(manager.queryByRole("button", { name: /^Delete/ })).toBeNull();
    expect(manager.getByText("You always keep at least one account.")).toBeInTheDocument();
  });

  it("shows the server's sentence when it refuses, in case another window already deleted the rest", async () => {
    engine({ "DELETE /api/v2/accounts/3": refuse("LAST_ACCOUNT", LAST) });
    const manager = await openManager();
    fireEvent.click(manager.getByRole("button", { name: "Delete Papa's HUF" }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(LAST);
  });
});

describe("deleting the account that is in view", () => {
  it("goes back to all accounts, so the screen is never left on an account that is gone", async () => {
    engine({ "DELETE /api/v2/accounts/3": { deleted: true, moved: 0 } });
    const manager = await openManager("/portfolio?account=3");
    fireEvent.click(manager.getByRole("button", { name: "Delete Papa's HUF" }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete account" }));
    await screen.findByText("Deleted “Papa's HUF”.");
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/portfolio?account=all"));
    expect(localStorage.getItem("quantos.portfolio.account")).toBe("all");
  });
});
