import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, test, vi } from "vitest";
import { ACCOUNT_LINES } from "./portfolioKit";
import { AccountCards } from "./AccountCards";

afterEach(cleanup);

function show() {
  const onChoose = vi.fn();
  render(<AccountCards accounts={ACCOUNT_LINES} onChoose={onChoose} />);
  return onChoose;
}
const card = (name: string) => within(screen.getByRole("button", { name: `Show only ${name}` }));

const FACTS: [string, string][] = [
  ["My account", "Me · Demat account"],
  ["My account", "₹1,200"],
  ["My account", "+₹200"],
  ["My account", "+20.0%"],
  ["My account", "1 holding"],
  ["My account", "40% of everything you hold"],
  ["Asha's Zerodha", "Asha · Demat account · Zerodha"],
  ["Asha's Zerodha", "₹1,800"],
  ["Asha's Zerodha", "+₹300"],
  ["Asha's Zerodha", "2 holdings"],
  ["Asha's Zerodha", "60% of everything you hold"],
  ["Papa's HUF", "Papa · HUF account"],
  ["Papa's HUF", "₹0"],
  ["Papa's HUF", "No holdings yet"],
  ["Papa's HUF", "0% of everything you hold"],
];

const CARDS: [string, string][] = [
  ["My account", "1"],
  ["Asha's Zerodha", "2"],
  ["Papa's HUF", "3"],
];

describe("the account cards", () => {
  it("has one card for each account", () => {
    show();
    expect(within(screen.getByRole("list", { name: "Your accounts" })).getAllByRole("listitem")).toHaveLength(3);
  });

  test.each(FACTS)("%s shows %s", (name, text) => {
    show();
    expect(card(name).getByText(text)).toBeInTheDocument();
  });

  it("does not show a gain for an account with nothing in it", () => {
    show();
    expect(card("Papa's HUF").queryByText(/^[+−]/)).toBeNull();
  });

  test.each(CARDS)("chooses %s when its card is pressed", (name, id) => {
    const onChoose = show();
    fireEvent.click(screen.getByRole("button", { name: `Show only ${name}` }));
    expect(onChoose).toHaveBeenCalledWith(id);
  });
});
