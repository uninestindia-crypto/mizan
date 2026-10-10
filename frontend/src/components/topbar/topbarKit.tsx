import { vi } from "vitest";
import { INSTALL, NEWER, SAME, serve, stage, UPDATE } from "../update/updateKit";

// Shared set-up for the top bar tests: the engine's answers for the calls the bar makes.

export const WED_MORNING_IN_INDIA = new Date("2026-10-07T05:00:00Z"); // 10:30, inside trading hours

const SETTINGS = { onboarding_complete: true, theme: "system", shariah_mode: false };
const IDLE_JOB = { job: { state: "IDLE" } };

export function statusAnswer(latestSession: string | null = "2026-10-06") {
  const index = { ready: latestSession !== null, latest_session: latestSession ?? undefined, ...IDLE_JOB };
  return {
    version: "2.5.0",
    settings: SETTINGS,
    index,
    download: { state: "IDLE", done: 0, total: 0 },
    data_folder: { scan: "IDLE" },
    lab_runs: 0,
  };
}

export const LIVE_ON = { live_prices: { ready: true, message: null } };
export const LIVE_OFF = {
  live_prices: { ready: false, message: "Add your Upstox key in Settings, then Accounts and keys." },
};

interface Engine {
  update?: unknown;
  live?: unknown;
  status?: unknown;
  /** The exchange's holiday list. When it is left out the engine has no answer for it, as when the list is missing. */
  holidays?: unknown;
}

/** The exchange's holidays as the engine sends them: 2026, with Wednesday 7 October an ordinary day. */
export const HOLIDAYS_2026 = {
  years: [2026],
  holidays: [
    { date: "2026-10-02", name: "Mahatma Gandhi Jayanti" },
    { date: "2026-10-20", name: "Dussehra" },
  ],
};

/** The engine for a top bar: a status, an update notice, the live-price answer, and nothing under way. */
export function engine({ update = SAME, live = LIVE_ON, status = statusAnswer(), holidays }: Engine = {}): void {
  serve({
    "GET /api/v2/status": status,
    [`GET ${UPDATE}`]: update,
    "GET /api/v2/copilot/status": live,
    [`GET ${INSTALL}`]: stage("idle"),
    ...(holidays === undefined ? {} : { "GET /api/v2/market/holidays": holidays }),
  });
}

export const withUpdate = () => engine({ update: NEWER });

/** Pretends the bar is this many pixels wide, since a test window has no layout. */
export function barWidth(width: number) {
  return vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
    width,
    height: 56,
    top: 0,
    left: 0,
    right: width,
    bottom: 56,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  });
}
