import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { callsTo, deferred, routeApi } from "../agents/testHarness";
import { ApiError, api } from "../../lib/api";
import { ModeNotice, ModeSwitch, PhoneModeButton } from "./ModeSwitch";
import { renderPage, statusFor } from "./modeKit";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

let saved = false;

function save(put: (body: unknown) => unknown, body: unknown): unknown {
  const reply = put(body);
  saved = (body as { shariah_mode: boolean }).shariah_mode;
  return reply;
}

function engine(put: (body: unknown) => unknown = () => ({})) {
  routeApi({
    "GET /api/v2/status": () => statusFor(saved),
    "PUT /api/v2/settings": (body: unknown) => save(put, body),
  });
}

const page = (
  <>
    <ModeSwitch />
    <PhoneModeButton />
    <ModeNotice />
  </>
);
const radio = (name: string) => screen.getByRole("radio", { name });

beforeEach(() => {
  vi.mocked(api).mockReset();
  saved = false;
});
afterEach(cleanup);

describe("the mode is the saved setting", () => {
  const CASES_1 = [
    [false, "/shariah", "Institutional QuantOS"],
    [true, "/", "Mizan Shariah"],
  ] as const;

  it.each(CASES_1)("with the setting %s at %s the checked mode is %s", async (shariah, path, name) => {
    saved = shariah;
    engine();
    renderPage(page, path);
    await waitFor(() => expect(radio(name)).toHaveAttribute("aria-checked", "true"));
  });

  it("does not change the mode just because a Shariah page is open", async () => {
    engine();
    renderPage(page, "/shariah");
    await screen.findByRole("radio", { name: "Institutional QuantOS" });
    expect(radio("Institutional QuantOS")).toHaveAttribute("aria-checked", "true");
    expect(callsTo("PUT", "/api/v2/settings")).toHaveLength(0);
  });
});

describe("the same setting from other screens", () => {
  it("moves the switch when Settings or the welcome steps save the setting", async () => {
    engine();
    const { client } = renderPage(page);
    await waitFor(() => expect(radio("Institutional QuantOS")).toHaveAttribute("aria-checked", "true"));
    saved = true;
    await act(() => client.invalidateQueries({ queryKey: ["status"] }));
    await waitFor(() => expect(radio("Mizan Shariah")).toHaveAttribute("aria-checked", "true"));
  });
});

describe("switching", () => {
  it("shows the new mode at once, saves the setting, then goes to that mode's home", async () => {
    const slow = deferred<unknown>();
    engine(() => slow.promise);
    renderPage(page, "/stock/TCS");
    fireEvent.click(await screen.findByRole("radio", { name: "Mizan Shariah" }));
    await waitFor(() => expect(radio("Mizan Shariah")).toHaveAttribute("aria-checked", "true"));
    expect(screen.getByTestId("where")).toHaveTextContent("/shariah");
    await waitFor(() => expect(callsTo("PUT", "/api/v2/settings")).toEqual([{ shariah_mode: true }]));
    slow.resolve({});
  });

  it("goes back to Institutional QuantOS home and writes false", async () => {
    saved = true;
    engine();
    renderPage(page, "/shariah");
    await waitFor(() => expect(radio("Mizan Shariah")).toHaveAttribute("aria-checked", "true"));
    fireEvent.click(radio("Institutional QuantOS"));
    await waitFor(() => expect(callsTo("PUT", "/api/v2/settings")).toEqual([{ shariah_mode: false }]));
    expect(screen.getByTestId("where")).toHaveTextContent(/^\/$/);
  });

  it("goes back to the old mode and says so in plain words when saving fails", async () => {
    engine(() => {
      throw new ApiError("HTTP_500", "broken", 500);
    });
    renderPage(page, "/stock/TCS");
    fireEvent.click(await screen.findByRole("radio", { name: "Mizan Shariah" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Could not switch to Mizan Shariah, so QuantOS is still in Institutional QuantOS.");
    expect(radio("Institutional QuantOS")).toHaveAttribute("aria-checked", "true");
    expect(radio("Mizan Shariah")).toHaveAttribute("aria-checked", "false");
  });

  it("lets the person dismiss the failure message", async () => {
    engine(() => {
      throw new ApiError("HTTP_500", "broken", 500);
    });
    renderPage(page);
    fireEvent.click(await screen.findByRole("radio", { name: "Mizan Shariah" }));
    fireEvent.click(within(await screen.findByRole("alert")).getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("says the new mode aloud", async () => {
    engine();
    renderPage(page);
    fireEvent.click(await screen.findByRole("radio", { name: "Mizan Shariah" }));
    expect(await screen.findByText("Switched to Mizan Shariah.")).toBeInTheDocument();
  });
});

describe("keyboard and screen reader", () => {
  it("is a radio group with one stop, and an arrow key picks the other mode and keeps focus there", async () => {
    engine();
    renderPage(page);
    const quant = await screen.findByRole("radio", { name: "Institutional QuantOS" });
    expect(screen.getByRole("radiogroup", { name: "Application Mode" })).toBeInTheDocument();
    expect(quant).toHaveAttribute("tabindex", "0");
    expect(radio("Mizan Shariah")).toHaveAttribute("tabindex", "-1");
    quant.focus();
    fireEvent.keyDown(quant, { key: "ArrowRight" });
    await waitFor(() => expect(callsTo("PUT", "/api/v2/settings")).toEqual([{ shariah_mode: true }]));
    expect(radio("Mizan Shariah")).toHaveFocus();
    expect(radio("Mizan Shariah")).toHaveAttribute("tabindex", "0");
  });

  const CASES_2 = [
    [false, "Institutional QuantOS mode. Switch to Mizan Shariah"],
    [true, "Mizan Shariah mode. Switch to Institutional QuantOS"],
  ] as const;

  it.each(CASES_2)("names the phone button for the mode %s", async (shariah, name) => {
    saved = shariah;
    engine();
    renderPage(page);
    expect(await screen.findByRole("button", { name })).toBeInTheDocument();
  });

  it("switches from the phone button", async () => {
    engine();
    renderPage(page);
    fireEvent.click(await screen.findByRole("button", { name: /Switch to Mizan Shariah/ }));
    await waitFor(() => expect(callsTo("PUT", "/api/v2/settings")).toEqual([{ shariah_mode: true }]));
    expect(screen.getByTestId("where")).toHaveTextContent("/shariah");
  });
});
