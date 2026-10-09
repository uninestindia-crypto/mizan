import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, test, vi } from "vitest";
import type { AccountLine } from "../../lib/types";
import { ACCOUNT_LINES } from "./portfolioKit";
import { AccountSwitcher, MAX_SIDE_BY_SIDE } from "./AccountSwitcher";

afterEach(cleanup);

function manyAccounts(count: number): AccountLine[] {
  const template = ACCOUNT_LINES[0]!;
  return Array.from({ length: count }, (_, i) => ({
    ...template,
    id: i + 1,
    name: `Account ${i + 1}`,
    owner: i === 6 ? "Rekha" : "Me",
    value: (i + 1) * 1000,
  }));
}

function show(accounts: AccountLine[], choice = "all") {
  const onChoose = vi.fn();
  render(<AccountSwitcher accounts={accounts} choice={choice} onChoose={onChoose} />);
  return onChoose;
}

const MARKED: [string, string][] = [
  ["all", "All accounts"],
  ["2", "Asha's Zerodha"],
];

const ARROWS: [string, string, string][] = [
  ["ArrowRight", "all", "1"],
  ["ArrowLeft", "all", "3"],
  ["ArrowDown", "1", "2"],
  ["ArrowUp", "1", "all"],
];

describe("a few accounts", () => {
  it("shows All accounts and each account as a button with its kind and value", () => {
    show(ACCOUNT_LINES);
    const group = within(screen.getByRole("radiogroup", { name: "Choose an account" }));
    expect(group.getAllByRole("radio").map((r) => r.textContent)).toEqual([
      "All accounts₹3,000",
      "My accountDemat account · ₹1,200",
      "Asha's ZerodhaDemat account · ₹1,800",
      "Papa's HUFHUF account · ₹0",
    ]);
  });

  test.each(MARKED)("marks %s as the one in view", (choice, name) => {
    show(ACCOUNT_LINES, choice);
    expect(screen.getByRole("radio", { name: new RegExp(name) })).toBeChecked();
    expect(screen.getAllByRole("radio", { checked: true })).toHaveLength(1);
  });

  it("chooses an account when its button is pressed", () => {
    const onChoose = show(ACCOUNT_LINES);
    fireEvent.click(screen.getByRole("radio", { name: /Papa's HUF/ }));
    expect(onChoose).toHaveBeenCalledWith("3");
  });

  test.each(ARROWS)("%s from %s moves to %s", (key, from, to) => {
    const onChoose = show(ACCOUNT_LINES, from);
    fireEvent.keyDown(screen.getByRole("radio", { checked: true }), { key });
    expect(onChoose).toHaveBeenCalledWith(to);
  });

  it("can be reached with Tab on the chosen button only", () => {
    show(ACCOUNT_LINES, "2");
    const reachable = screen.getAllByRole("radio").filter((r) => r.tabIndex === 0);
    expect(reachable.map((r) => r.textContent)).toEqual(["Asha's ZerodhaDemat account · ₹1,800"]);
  });
});

describe("many accounts", () => {
  const MANY = manyAccounts(MAX_SIDE_BY_SIDE + 2);
  const TYPED: [string, string[]][] = [
    ["account 7", ["Account 7"]],
    ["rekha", ["Account 7"]],
    ["demat", MANY.map((a) => a.name)],
  ];
  const openList = () => fireEvent.click(screen.getByRole("button", { name: /Account/ }));

  it("shows one button for the account in view instead of a row of buttons", () => {
    show(MANY, "3");
    expect(screen.queryByRole("radiogroup")).toBeNull();
    expect(screen.getByRole("button", { name: /Account 3/ })).toHaveAttribute("aria-expanded", "false");
  });

  it("opens a list of every account, and All accounts first, with the search ready", () => {
    show(MANY);
    openList();
    const options = within(screen.getByRole("listbox", { name: "Accounts" })).getAllByRole("option");
    expect(options).toHaveLength(MANY.length + 1);
    expect(options[0]).toHaveTextContent("All accounts");
    expect(screen.getByRole("combobox", { name: "Find an account" })).toHaveFocus();
  });

  test.each(TYPED)("finds accounts by typing %s", (text, found) => {
    show(MANY);
    openList();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: text } });
    const names = screen.getAllByRole("option").map((o) => o.querySelector("span > span")?.textContent);
    expect(names).toEqual(found);
  });

  it("says when nothing matches", () => {
    show(MANY);
    openList();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "zzz" } });
    expect(screen.getByRole("status")).toHaveTextContent("No account matches “zzz”.");
  });

  it("chooses with the arrow keys and Enter, then closes and gives focus back", () => {
    const onChoose = show(MANY);
    openList();
    const search = screen.getByRole("combobox");
    fireEvent.keyDown(search, { key: "ArrowDown" });
    fireEvent.keyDown(search, { key: "ArrowDown" });
    fireEvent.keyDown(search, { key: "Enter" });
    expect(onChoose).toHaveBeenCalledWith("2");
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(screen.getByRole("button", { name: /Account/ })).toHaveFocus();
  });

  it("closes with Escape without choosing", () => {
    const onChoose = show(MANY);
    openList();
    fireEvent.keyDown(screen.getByRole("combobox"), { key: "Escape" });
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(onChoose).not.toHaveBeenCalled();
  });

  it("chooses an account when it is clicked", () => {
    const onChoose = show(MANY);
    openList();
    fireEvent.click(screen.getByRole("option", { name: /Account 5/ }));
    expect(onChoose).toHaveBeenCalledWith("5");
  });
});
