import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, test, vi } from "vitest";
import { callsTo } from "../agents/testHarness";
import { api } from "../../lib/api";
import { ACCOUNT_LIST, LOT_TCS_ASHA, engine, renderAt } from "./portfolioKit";
import { HoldingFormDialog, draftFromRow } from "./HoldingFormDialog";
import { ACCOUNTS_KEY, type AccountChoice } from "./accountQueries";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

const NEW_TCS = { symbol: "TCS", quantity: "4", avg_price: "3800", buy_date: "2026-03-01" };
const SAVED = { "POST /api/v2/portfolio/holdings": {}, "PUT /api/v2/portfolio/holdings/2": {} };

function openForm(viewing: AccountChoice, initial: object = NEW_TCS) {
  return renderAt(<HoldingFormDialog open onOpenChange={() => undefined} initial={initial} viewing={viewing} />);
}
const accountSelect = () => screen.findByLabelText("Account");
const save = (name: string) => fireEvent.click(screen.getByRole("button", { name }));
function posted() {
  return callsTo("POST", "/api/v2/portfolio/holdings")[0] as Record<string, unknown>;
}

const VIEWS: [AccountChoice, number, string][] = [
  ["all", 1, "the first account, My account, when every account is in view"],
  ["2", 2, "the account in view"],
  ["3", 3, "the account in view, even one with nothing in it"],
];

describe("adding a holding", () => {
  test.each(VIEWS)("viewing %s sends account %i: %s", async (viewing, expected) => {
    engine(SAVED);
    openForm(viewing);
    expect(await accountSelect()).toHaveValue(String(expected));
    save("Add holding");
    await vi.waitFor(() => expect(posted().account_id).toBe(expected));
  });

  it("sends the account that was picked instead", async () => {
    engine(SAVED);
    openForm("all");
    fireEvent.change(await accountSelect(), { target: { value: "3" } });
    save("Add holding");
    await vi.waitFor(() => expect(posted()).toMatchObject({ symbol: "TCS", quantity: 4, account_id: 3 }));
  });

  it("lists every account by name and owner", async () => {
    engine(SAVED);
    openForm("all");
    const names = Array.from((await accountSelect()).querySelectorAll("option"), (o) => o.textContent);
    expect(names).toEqual(ACCOUNT_LIST.accounts.map((a) => `${a.name} (${a.owner})`));
  });
});

describe("with one account only", () => {
  const lonely = { "GET /api/v2/accounts": { accounts: [ACCOUNT_LIST.accounts[0]], kinds: ACCOUNT_LIST.kinds } };

  it("shows no Account choice, and still sends the account", async () => {
    engine({ ...SAVED, ...lonely });
    const { client } = openForm("all");
    await vi.waitFor(() => expect(client.getQueryData(ACCOUNTS_KEY)).toBeDefined());
    save("Add holding");
    await vi.waitFor(() => expect(posted().account_id).toBe(1));
    expect(screen.queryByLabelText("Account")).toBeNull();
  });
});

describe("changing a holding", () => {
  it("starts on the account the purchase is in, and moving it sends the new account", async () => {
    engine(SAVED);
    openForm("all", draftFromRow(LOT_TCS_ASHA));
    const select = await accountSelect();
    expect(select).toHaveValue("2");
    fireEvent.change(select, { target: { value: "1" } });
    save("Save changes");
    await vi.waitFor(() => expect(callsTo("PUT", "/api/v2/portfolio/holdings/2")).toHaveLength(1));
    expect(callsTo("PUT", "/api/v2/portfolio/holdings/2")[0]).toMatchObject({ account_id: 1, quantity: 5 });
  });

  it("keeps the purchase where it is when the account is left alone", async () => {
    engine(SAVED);
    openForm("1", draftFromRow(LOT_TCS_ASHA));
    expect(await accountSelect()).toHaveValue("2");
    save("Save changes");
    await vi.waitFor(() => expect(callsTo("PUT", "/api/v2/portfolio/holdings/2")[0]).toMatchObject({ account_id: 2 }));
  });
});
