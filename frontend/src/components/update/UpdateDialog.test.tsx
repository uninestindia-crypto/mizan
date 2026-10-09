import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../../lib/api";
import { callsTo, INSTALL, inTurn, NEWER, renderPage, SAME, serve, stage, UPDATE } from "./updateKit";
import { UpdateDialog } from "./UpdateDialog";
import { WINDOWS_NOTE } from "./updateInstall";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

const NOTHING_NEWER =
  "There is no newer version to install right now. Check for updates first, " +
  "or open the release page to get the installer yourself.";

function open(onOpenChange = vi.fn()) {
  renderPage(<UpdateDialog open onOpenChange={onOpenChange} />);
  return onOpenChange;
}
const button = (name: string) => screen.getByRole("button", { name });
const bar = () => screen.getByRole("progressbar", { name: "Download progress" });

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("an update is waiting and nothing has started", () => {
  beforeEach(() => {
    serve({ [`GET ${UPDATE}`]: NEWER, [`GET ${INSTALL}`]: stage("idle") });
  });

  it("names the new version and what version the person has", async () => {
    open();
    expect(await screen.findByText("QuantOS 2.6.0 is ready")).toBeInTheDocument();
    expect(screen.getByText(/You have version 2\.5\.0\./)).toBeInTheDocument();
  });

  it("shows what is new as plain text, without the marks of a web page", async () => {
    open();
    const notes = await screen.findByRole("region", { name: "What is new" });
    expect(within(notes).getByText(/• Search now finds pages as well as stocks/)).toBeInTheDocument();
    expect(notes.textContent).not.toMatch(/\*\*|##/);
  });

  it("says once, before the button, that Windows may ask the person to confirm", async () => {
    open();
    expect(await screen.findAllByText(WINDOWS_NOTE)).toHaveLength(1);
  });

  it("offers Update and restart and Not now, with the release page link beside What is new", async () => {
    open();
    const notes = await screen.findByRole("region", { name: "What is new" });
    expect(button("Update and restart")).toBeEnabled();
    expect(button("Not now")).toBeEnabled();
    expect(within(notes).getByRole("link", { name: /Open the release page/ })).toHaveAttribute("href", NEWER.url);
  });

  it("does not repeat the heading or the title that the notes carry for a web page", async () => {
    const notes = "# QuantOS v2.6.0\n\n## What's new\n- One change";
    serve({ [`GET ${UPDATE}`]: { ...NEWER, notes }, [`GET ${INSTALL}`]: stage("idle") });
    open();
    const region = await screen.findByRole("region", { name: "What is new" });
    expect(within(region).getAllByText(/What is new/)).toHaveLength(1);
    expect(region.textContent).not.toMatch(/QuantOS v2\.6\.0/);
  });

  it("closes from Not now", async () => {
    const onOpenChange = open();
    fireEvent.click(await screen.findByRole("button", { name: "Not now" }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});

describe("pressing Update and restart", () => {
  it("sends no body, so no address can be passed, and shows the download bar from the answer", async () => {
    const answers = { [`GET ${UPDATE}`]: NEWER, [`GET ${INSTALL}`]: stage("idle") };
    serve({ ...answers, [`POST ${INSTALL}`]: stage("downloading", 42) });
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Update and restart" }));
    await waitFor(() => expect(bar()).toHaveAttribute("aria-valuenow", "42"));
    expect(callsTo("POST", INSTALL)).toEqual([[INSTALL, "POST"]]);
  });

  it("shows the engine's own sentence when there is no newer version, and keeps the release link", async () => {
    const refuse = () => {
      throw new ApiError("NOTHING_TO_INSTALL", NOTHING_NEWER, 409);
    };
    serve({ [`GET ${UPDATE}`]: NEWER, [`GET ${INSTALL}`]: stage("idle"), [`POST ${INSTALL}`]: refuse });
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Update and restart" }));
    expect(await screen.findByText(NOTHING_NEWER)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open the release page/ })).toBeInTheDocument();
    expect(button("Update and restart")).toBeEnabled();
  });
});

describe("an update under way (seen as the dialog opens)", () => {
  it("shows the download as a bar with its percentage, and hides the Windows note and a second press", async () => {
    serve({ [`GET ${UPDATE}`]: NEWER, [`GET ${INSTALL}`]: stage("downloading", 63) });
    open();
    await waitFor(() => expect(bar()).toHaveAttribute("aria-valuenow", "63"));
    expect(screen.getByText("63%")).toBeInTheDocument();
    expect(screen.getByText("Downloading QuantOS 2.6.0.")).toBeInTheDocument();
    expect(screen.queryByText(WINDOWS_NOTE)).not.toBeInTheDocument();
    expect(button("Updating…")).toBeDisabled();
  });

  it("shows words only, with no bar, when the size is not known", async () => {
    serve({ [`GET ${UPDATE}`]: NEWER, [`GET ${INSTALL}`]: stage("downloading", null) });
    open();
    expect(await screen.findByText("Downloading QuantOS 2.6.0.")).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("says the download is being checked", async () => {
    serve({ [`GET ${UPDATE}`]: NEWER, [`GET ${INSTALL}`]: stage("checking") });
    open();
    expect(await screen.findByText("Checking that the download is genuine.")).toBeInTheDocument();
  });

  it("says QuantOS will close and open again, and shows no error", async () => {
    const message = "Installing the update. QuantOS will close and open again in a moment.";
    serve({ [`GET ${UPDATE}`]: NEWER, [`GET ${INSTALL}`]: stage("installing", null, message) });
    open();
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(button("Updating…")).toBeDisabled();
  });

  it("uses its own words for installing when the engine sends none", async () => {
    serve({ [`GET ${UPDATE}`]: NEWER, [`GET ${INSTALL}`]: stage("installing") });
    open();
    expect(await screen.findByText(/QuantOS will close and open again in a moment/)).toBeInTheDocument();
  });
});

describe("an update that stopped", () => {
  const message = "The update could not be downloaded. Check your internet connection and try again.";

  it("shows the engine's message, keeps the release link, and offers Try again", async () => {
    serve({ [`GET ${UPDATE}`]: NEWER, [`GET ${INSTALL}`]: stage("failed", null, message) });
    open();
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open the release page/ })).toHaveAttribute("href", NEWER.url);
    expect(button("Try again")).toBeEnabled();
    expect(screen.getByText(WINDOWS_NOTE)).toBeInTheDocument();
  });

  it("starts again from Try again", async () => {
    serve({
      [`GET ${UPDATE}`]: NEWER,
      [`GET ${INSTALL}`]: stage("failed", null, message),
      [`POST ${INSTALL}`]: stage("downloading", 1),
    });
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Try again" }));
    await waitFor(() => expect(bar()).toHaveAttribute("aria-valuenow", "1"));
    expect(screen.queryByText(message)).not.toBeInTheDocument();
  });
});

describe("looking again while it moves, and never after the install begins", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  const second = () => act(() => vi.advanceTimersByTimeAsync(1000));

  it("asks once a second through downloading and checking, then stops when installing starts", async () => {
    const installing = stage("installing", null, "Installing now.");
    const turns = [stage("downloading", 10), stage("downloading", 60), stage("checking"), installing];
    serve({ [`GET ${UPDATE}`]: NEWER, [`GET ${INSTALL}`]: inTurn(turns) });
    open();
    await waitFor(() => expect(bar()).toHaveAttribute("aria-valuenow", "10"));
    await second();
    await waitFor(() => expect(bar()).toHaveAttribute("aria-valuenow", "60"));
    await second();
    expect(await screen.findByText("Checking that the download is genuine.")).toBeInTheDocument();
    await second();
    expect(await screen.findByText("Installing now.")).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(10_000));
    expect(callsTo("GET", INSTALL)).toHaveLength(4);
  });

  it("shows no error when the engine goes away after installing began", async () => {
    const gone = new ApiError("ENGINE_OFFLINE", "Gone.", 0);
    const goesAway = inTurn<unknown>([stage("installing", null, "Installing now."), gone]);
    const answer = () => {
      const next = goesAway();
      if (next instanceof Error) throw next;
      return next;
    };
    serve({ [`GET ${UPDATE}`]: NEWER, [`GET ${INSTALL}`]: answer });
    open();
    expect(await screen.findByText("Installing now.")).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(10_000));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText("Gone.")).not.toBeInTheDocument();
  });
});

describe("when there is nothing to install", () => {
  it("says QuantOS is up to date and offers no button", async () => {
    serve({ [`GET ${UPDATE}`]: SAME, [`GET ${INSTALL}`]: stage("idle") });
    open();
    expect(await screen.findByText("QuantOS is up to date")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Update and restart" })).not.toBeInTheDocument();
  });

  it("asks the engine nothing about an update while it is closed", async () => {
    serve({ [`GET ${UPDATE}`]: NEWER, [`GET ${INSTALL}`]: stage("idle") });
    renderPage(<UpdateDialog open={false} onOpenChange={vi.fn()} />);
    await waitFor(() => expect(callsTo("GET", UPDATE)).toHaveLength(1));
    expect(callsTo("GET", INSTALL)).toHaveLength(0);
  });
});
