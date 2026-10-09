import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { callsTo, renderApp, routeApi } from "./agents/testHarness";
import { BrokerViewSettings } from "./BrokerViewSettings";

vi.mock("../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../lib/api")>();
  return { ...real, api: vi.fn() };
});

const ADDRESS = "http://127.0.0.1:47610/upstox/callback";
const LOGIN = "https://api.upstox.com/v2/login/authorization/dialog?response_type=code";
const BASE = {
  id: "upstox",
  label: "Upstox",
  set_up: true,
  connected: false,
  waiting_for_sign_in: false,
  key_ends_at: null,
  callback_address: ADDRESS,
  message: null,
};

function status(over: Record<string, unknown> = {}, assistant = false, available = true) {
  return { brokers: [{ ...BASE, ...over }], assistant_access: assistant, available };
}

const SNAPSHOT = {
  broker: "upstox",
  connected: false,
  view_only: true,
  label: "From your Upstox account. View only.",
  fetched_at: null,
  freshness: "NONE",
  message: null,
  totals: null,
  cash: null,
  holdings: [],
  positions: [],
  warnings: [],
  skipped: { holdings: 0, positions: 0 },
  notes: [],
};

function engine(current: () => unknown, extra: Record<string, unknown> = {}) {
  routeApi({
    "GET /api/v2/broker/status": () => current(),
    "GET /api/v2/broker/snapshot": SNAPSHOT as never,
    ...(extra as Record<string, never>),
  });
}

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

describe("Settings, Broker view", () => {
  it("says what the broker view does and does not do, before anything else", async () => {
    engine(() => status());
    renderApp(<BrokerViewSettings />);
    expect(await screen.findByText(/It cannot buy, sell, move money or change anything/)).toBeInTheDocument();
    expect(screen.getByText(/never asks for your trading PIN or password/)).toBeInTheDocument();
  });

  it("before the app keys are saved, shows the three steps, the exact return address, and a Connect that waits", async () => {
    engine(() => status({ set_up: false }));
    renderApp(<BrokerViewSettings />);
    expect(await screen.findByText("Open your Upstox app page")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open your Upstox app page/ })).toHaveAttribute("href", "https://service.upstox.com/developer/apps");
    expect(screen.getByText(ADDRESS)).toBeInTheDocument();
    expect(screen.getByText(/leave "Static IP" empty/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Settings, then Accounts and keys" })).toHaveAttribute("href", "/settings/accounts");
    expect(screen.getByRole("button", { name: "Connect Upstox" })).toBeDisabled();
    expect(screen.getByText("Save your Upstox app key and secret first.")).toBeInTheDocument();
  });

  it("copies the exact return address", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    engine(() => status({ set_up: false }));
    renderApp(<BrokerViewSettings />);
    fireEvent.click(await screen.findByRole("button", { name: "Copy" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(ADDRESS));
    expect(await screen.findByRole("button", { name: "Copied" })).toBeInTheDocument();
  });

  it("opens Upstox's sign-in on Connect, then waits with a way to cancel and a link in case no page opened", async () => {
    let current = status();
    engine(() => current, {
      "POST /api/v2/broker/upstox/connect": () => {
        current = status({ waiting_for_sign_in: true });
        return { opened: true, login_address: LOGIN };
      },
      "DELETE /api/v2/broker/upstox/connect": () => {
        current = status();
        return current;
      },
    });
    renderApp(<BrokerViewSettings />);
    fireEvent.click(await screen.findByRole("button", { name: "Connect Upstox" }));
    expect(await screen.findByText(/Sign in on the Upstox page that just opened in your browser/)).toBeInTheDocument();
    expect(screen.getAllByText(/QuantOS never sees your password/).length).toBeGreaterThan(0);
    expect(callsTo("POST", "/api/v2/broker/upstox/connect")).toHaveLength(1);
    const fallback = screen.getByRole("link", { name: /If no page opened, click here/ });
    expect(fallback).toHaveAttribute("href", LOGIN);
    expect(fallback).toHaveAttribute("rel", "noopener noreferrer");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(callsTo("DELETE", "/api/v2/broker/upstox/connect")).toHaveLength(1));
    expect(await screen.findByRole("button", { name: "Connect Upstox" })).toBeInTheDocument();
  });

  it("shows why a sign-in could not start, in the engine's own words", async () => {
    const { ApiError } = await import("../lib/api");
    vi.mocked(api).mockImplementation((async (path: string, method = "GET") => {
      if (path === "/api/v2/broker/status") return status();
      if (path === "/api/v2/broker/snapshot") return SNAPSHOT;
      if (method === "POST") throw new ApiError("CALLBACK_BUSY", "Close other programs, then click Connect Upstox again.", 409);
      return null;
    }) as never);
    renderApp(<BrokerViewSettings />);
    fireEvent.click(await screen.findByRole("button", { name: "Connect Upstox" }));
    expect(await screen.findByText("Close other programs, then click Connect Upstox again.")).toBeInTheDocument();
  });

  it("when connected, says when Upstox ends the sign-in and offers Refresh now and Disconnect", async () => {
    let current = status({ connected: true, key_ends_at: "2026-10-07T03:30:00+05:30" });
    engine(() => current, {
      "DELETE /api/v2/broker/connection": () => {
        current = status();
        return current;
      },
    });
    renderApp(<BrokerViewSettings />);
    expect(await screen.findByText(/Connected to Upstox\./)).toBeInTheDocument();
    expect(screen.getByText(/After that, click Connect Upstox again \(about 20 seconds\)/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh now" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Disconnect" }));
    await waitFor(() => expect(callsTo("DELETE", "/api/v2/broker/connection")).toHaveLength(1));
    expect(await screen.findByRole("button", { name: "Connect Upstox" })).toBeInTheDocument();
  });

  it("reads the figures again a moment after the sign-in is in force, because the first fetch runs just after it", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      engine(() => status({ connected: true, key_ends_at: "2026-10-07T03:30:00+05:30" }));
      renderApp(<BrokerViewSettings />);
      await screen.findByText(/Connected to Upstox\./);
      const before = callsTo("GET", "/api/v2/broker/snapshot").length;
      await vi.advanceTimersByTimeAsync(2_100);
      await waitFor(() => expect(callsTo("GET", "/api/v2/broker/snapshot").length).toBeGreaterThan(before));
    } finally {
      vi.useRealTimers();
    }
  });

  it("shows the engine's message when the sign-in has a problem", async () => {
    engine(() => status({ message: "Upstox did not accept the sign-in. Open Settings, then Broker view, and click Connect Upstox again." }));
    renderApp(<BrokerViewSettings />);
    expect(await screen.findByText(/Upstox did not accept the sign-in/)).toBeInTheDocument();
  });

  it("starts with the assistant switched off, and turns it on only when asked", async () => {
    let current = status();
    engine(() => current, {
      "PUT /api/v2/broker/assistant-access": (body: unknown) => {
        current = status({}, (body as { allowed: boolean }).allowed);
        return current;
      },
    });
    renderApp(<BrokerViewSettings />);
    const toggle = await screen.findByRole("switch", { name: "Let the assistant read my broker account" });
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(screen.getByText(/Your key and your account details are never sent/)).toBeInTheDocument();
    fireEvent.click(toggle);
    await waitFor(() => expect(callsTo("PUT", "/api/v2/broker/assistant-access")).toEqual([{ allowed: true }]));
    await waitFor(() => expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true"));
  });

  it("says plainly when it cannot be used on this computer", async () => {
    engine(() => status({}, false, false));
    renderApp(<BrokerViewSettings />);
    expect(await screen.findByText("Not available on this computer")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Connect Upstox" })).toBeNull();
  });

  it("has no button that could trade, in any state", async () => {
    for (const current of [status({ set_up: false }), status(), status({ waiting_for_sign_in: true }), status({ connected: true })]) {
      vi.mocked(api).mockReset();
      engine(() => current);
      const view = renderApp(<BrokerViewSettings />);
      await screen.findByText("View only");
      const names = screen.getAllByRole("button").map((b) => b.textContent ?? "");
      expect(names.filter((name) => /\b(buy|sell|place|exit|convert|order|trade)\b/i.test(name))).toEqual([]);
      view.unmount();
    }
  });

  it("never uses a developer's word", async () => {
    engine(() => status({ set_up: false }));
    const { container } = renderApp(<BrokerViewSettings />);
    await screen.findByText("Open your Upstox app page");
    expect(container.textContent ?? "").not.toMatch(/\b(API|JSON|token|terminal|command|backend|endpoint|\.env)\b/i);
  });
});
