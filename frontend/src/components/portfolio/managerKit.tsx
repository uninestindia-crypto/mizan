import { fireEvent, screen, within } from "@testing-library/react";
import Portfolio from "../../pages/Portfolio";
import { ApiError } from "../../lib/api";
import { renderAt } from "./portfolioKit";

// Helpers for the tests of the Manage accounts window.

export const refuse = (code: string, message: string) => () => {
  throw new ApiError(code, message, 400);
};

export async function openManager(path = "/portfolio") {
  renderAt(<Portfolio />, path);
  const opener = await screen.findByRole("button", { name: "Manage accounts" });
  opener.focus(); // a click focuses its button in a browser, and the window hands focus back to it
  fireEvent.click(opener);
  const dialog = within(await screen.findByRole("dialog", { name: "Your accounts" }));
  await dialog.findByRole("list", { name: "Your accounts" });
  return dialog;
}
export const type = (label: string, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });

