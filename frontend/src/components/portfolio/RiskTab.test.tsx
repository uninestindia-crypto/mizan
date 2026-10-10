import { cleanup, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { renderApp, routeApi } from "../agents/testHarness";
import { TooltipProvider } from "../ui";
import type { TabContext } from "./PortfolioTabs";
import { RiskTab } from "./RiskTab";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

const NOTHING = { available: false, message: "There are no holdings to look at yet.", window: null, volatility_pct: null, effective_bets: null, diversification: null, shrinkage: null, holdings: [], left_out: [], note: "" };
const context = (choice: string) => ({ data: {}, choice, showAccounts: true, onEdit: vi.fn(), onRemove: vi.fn() }) as unknown as TabContext;

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

describe("the Risk tab", () => {
  it("looks at every account together when all accounts are in view", async () => {
    routeApi({ "GET /api/v2/portfolio/risk": NOTHING });
    renderApp(<TooltipProvider><RiskTab {...context("all")} /></TooltipProvider>);
    expect(await screen.findByText("There are no holdings to look at yet.")).toBeInTheDocument();
  });

  it("looks at one account when that account is in view", async () => {
    routeApi({ "GET /api/v2/portfolio/risk?account=7": NOTHING });
    renderApp(<TooltipProvider><RiskTab {...context("7")} /></TooltipProvider>);
    expect(await screen.findByText("There are no holdings to look at yet.")).toBeInTheDocument();
  });
});
