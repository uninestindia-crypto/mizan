import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";
import { api } from "../../lib/api";
import type { UpdateInfo } from "../../lib/types";
import { TooltipProvider } from "../ui";
import type { InstallStatus } from "./updateInstall";

// Shared set-up for the update window's tests: a fake engine that answers by route, and a page to render into.
// The test file replaces `api` with `vi.fn()` (vi.mock("../../lib/api", ...)) before using any of this.

export const INSTALL = "/api/v2/updates/install";
export const UPDATE = "/api/v2/update";

export const NEWER: UpdateInfo = {
  current: "2.5.0",
  latest: "2.6.0",
  update_available: true,
  url: "https://example.test/releases/v2.6.0",
  notes:
    "## What is new\n\n- **Search** now finds pages as well as stocks\n- The top bar tells you when the market is open",
  published_at: "2026-10-06T10:00:00Z",
  installer: "QuantOS_v2.6.0_Setup.exe",
  checked: true,
};
export const SAME: UpdateInfo = { ...NEWER, latest: "2.5.0", update_available: false, notes: "" };

export function stage(state: InstallStatus["state"], percent: number | null = null, message = ""): InstallStatus {
  return { state, percent, message, version: "2.6.0" };
}

type Answer = unknown | (() => unknown);

/** Answers each "METHOD /path" from the table (a function is called, and may throw). Anything else fails loudly. */
export function serve(table: Record<string, Answer>): void {
  vi.mocked(api).mockImplementation((async (path: string, method = "GET") => {
    const answer = table[`${method} ${path}`];
    if (answer === undefined) throw new Error(`No answer set for ${method} ${path}`);
    return typeof answer === "function" ? (answer as () => unknown)() : answer;
  }) as never);
}

/** Every call made to one route, as the arguments the page passed (so a call with no body has no third argument). */
export function callsTo(method: string, path: string): unknown[][] {
  return vi.mocked(api).mock.calls.filter(([p, m = "GET"]) => p === path && m === method);
}

/** Hands out the answers one by one, repeating the last. */
export function inTurn<T>(answers: readonly T[]): () => T {
  let next = 0;
  return () => answers[Math.min(next++, answers.length - 1)] as T;
}

const QUIET = { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } };

export function renderPage(ui: ReactElement, path = "/") {
  const client = new QueryClient({ defaultOptions: QUIET });
  return render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  );
}
