import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { INSTALL, NEWER, renderPage, SAME, serve, stage, UPDATE } from "./updateKit";
import { UpdateNowButton } from "./UpdateNowButton";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

describe("the Update and restart button for a screen with room for one", () => {
  it("shows nothing when there is no newer version", async () => {
    serve({ [`GET ${UPDATE}`]: SAME, [`GET ${INSTALL}`]: stage("idle") });
    renderPage(<UpdateNowButton />);
    await waitFor(() => expect(vi.mocked(api)).toHaveBeenCalledWith(UPDATE));
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("offers Update and restart when a newer version is out, and opens the update window", async () => {
    serve({ [`GET ${UPDATE}`]: NEWER, [`GET ${INSTALL}`]: stage("idle") });
    renderPage(<UpdateNowButton />);
    fireEvent.click(await screen.findByRole("button", { name: "Update and restart" }));
    expect(await screen.findByText("QuantOS 2.6.0 is ready")).toBeInTheDocument();
  });

  it("says how far the update has got instead, while one is under way", async () => {
    serve({ [`GET ${UPDATE}`]: NEWER, [`GET ${INSTALL}`]: stage("downloading", 42) });
    renderPage(<UpdateNowButton />);
    expect(await screen.findByRole("button", { name: "Updating 42%" })).toBeInTheDocument();
  });

  it("gives focus back to the button when the window is closed", async () => {
    serve({ [`GET ${UPDATE}`]: NEWER, [`GET ${INSTALL}`]: stage("idle") });
    renderPage(<UpdateNowButton />);
    const button = await screen.findByRole("button", { name: "Update and restart" });
    button.focus();
    fireEvent.click(button);
    fireEvent.click(await screen.findByRole("button", { name: "Not now" }));
    await waitFor(() => expect(button).toHaveFocus());
  });
});
