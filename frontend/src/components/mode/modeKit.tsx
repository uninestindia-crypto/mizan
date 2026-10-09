import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, useLocation } from "react-router";
import { ApiError } from "../../lib/api";
import { TooltipProvider } from "../ui";
import { routeApi } from "../agents/testHarness";

// Shared set-up for the Shariah-mode screen tests: the app's answers for each mode, and a page to render into.

const INDEX = { ready: true, latest_session: "2026-10-05", job: { state: "IDLE" } };
const SETTINGS = { onboarding_complete: true, theme: "system" };

export function statusFor(shariah: boolean) {
  const settings = { ...SETTINGS, shariah_mode: shariah };
  return { settings, index: INDEX, download: { state: "IDLE" }, data_folder: { scan: "IDLE" }, lab_runs: 0 };
}

export interface Row {
  verdict: string;
  data_status: string;
  short: string;
  as_of: string | null;
}

export const COMPLIANT_ROW: Row = {
  verdict: "COMPLIANT",
  data_status: "VERIFIED_FILING",
  short: "Passes every test.",
  as_of: "2024-09-30",
};
export const NON_COMPLIANT_ROW: Row = {
  verdict: "NON_COMPLIANT",
  data_status: "VERIFIED_FILING",
  short: "Debt is over the limit.",
  as_of: "2024-09-30",
};
export const QUESTIONABLE_ROW: Row = {
  verdict: "QUESTIONABLE",
  data_status: "UNVERIFIED_SAMPLE",
  short: "The standards disagree.",
  as_of: null,
};
export const NOT_SCREENED_ROW: Row = {
  verdict: "NOT_SCREENED",
  data_status: "NOT_SCREENED",
  short: "Not screened yet.",
  as_of: null,
};

/** The answer to the status call for these stocks. */
export const statuses = (rows: Record<string, Row>) => ({ statuses: rows });

/** The URL the status call is made on, for these stocks. */
export const statusUrl = (...symbols: string[]) =>
  `GET /api/v2/shariah/status?symbols=${[...symbols].sort().join(",")}`;

export function engineWith(shariah: boolean, more: Record<string, unknown> = {}) {
  routeApi({ "GET /api/v2/status": statusFor(shariah), ...more });
}

export const notFound = () => {
  throw new ApiError("HTTP_404", "Not Found", 404);
};

function Where() {
  return <span data-testid="where">{useLocation().pathname + useLocation().hash}</span>;
}

const QUIET = { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } };

export function renderPage(ui: ReactElement, path = "/start") {
  const client = new QueryClient({ defaultOptions: QUIET });
  const view = render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <MemoryRouter initialEntries={[path]}>
          {ui}
          <Where />
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  );
  return { client, ...view };
}
