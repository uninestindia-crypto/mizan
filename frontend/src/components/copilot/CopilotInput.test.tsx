import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../../lib/api";
import { box, CHAT, chatWith, openDrawer, reply, say, Shell } from "./chatTestKit";
import { callsTo, renderApp, routeApi } from "./testHarness";

vi.mock("../../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../lib/api")>();
  return { ...original, api: vi.fn() };
});

describe("the message box", () => {
  beforeEach(() => {
    vi.mocked(api).mockReset();
  });
  afterEach(cleanup);

  const typed = (length: number) => fireEvent.change(box(), { target: { value: "x".repeat(length) } });

  it("takes up to 4,000 characters and says nothing about length until it is nearly full", async () => {
    renderApp(<Shell />);
    openDrawer();
    await screen.findByRole("dialog");
    expect(box()).toHaveAttribute("maxlength", "4000");
    typed(3500);
    expect(screen.queryByText(/of 4,000/)).toBeNull();
  });

  it("shows a counter past 3,500 and a plain sentence at the limit", async () => {
    renderApp(<Shell />);
    openDrawer();
    await screen.findByRole("dialog");
    typed(3800);
    expect(screen.getByText("3,800 of 4,000")).toBeInTheDocument();
    typed(4000);
    const limit = "You have reached the limit of 4,000 characters. Shorten the message to add more.";
    expect(within(screen.getByRole("dialog")).getByRole("status")).toHaveTextContent(limit);
  });

  it("sends a long message whole, up to the limit", async () => {
    chatWith(reply());
    renderApp(<Shell />);
    openDrawer();
    await screen.findByRole("dialog");
    typed(3900);
    fireEvent.keyDown(box(), { key: "Enter" });
    await screen.findByText("TCS passes both standards.");
    expect(callsTo("POST", CHAT)[0]?.[2]).toMatchObject({ messages: [{ content: "x".repeat(3900) }] });
  });
});

describe("when the engine cannot read a message", () => {
  beforeEach(() => {
    vi.mocked(api).mockReset();
  });
  afterEach(cleanup);

  it("shows the engine's own sentence, with no Retry, and puts the message back in the box", async () => {
    const sentence = "Your message is too long for the Copilot. Shorten it and send it again.";
    routeApi({
      [`POST ${CHAT}`]: () => {
        throw new ApiError("BAD_REQUEST", sentence, 422, {});
      },
    });
    renderApp(<Shell />);
    openDrawer();
    await screen.findByRole("dialog");
    await say("a message the engine refuses");
    expect(await screen.findByText(sentence)).toBeInTheDocument();
    expect(screen.queryByText(/could not answer just now/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect(box()).toHaveValue("a message the engine refuses");
    expect(screen.queryByText("a message the engine refuses", { selector: "p" })).toBeNull();
  });

  it("keeps the generic line and Retry for a crash, and never shows its words", async () => {
    routeApi({
      [`POST ${CHAT}`]: () => {
        throw new ApiError("INTERNAL_ERROR", "Traceback KeyError 'x'", 500);
      },
    });
    renderApp(<Shell />);
    openDrawer();
    await screen.findByRole("dialog");
    await say("hello");
    expect(await screen.findByText(/The Copilot could not answer just now/)).toBeInTheDocument();
    expect(screen.queryByText(/Traceback/)).toBeNull();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
