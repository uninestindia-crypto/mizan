import { useState } from "react";
import { Card, CardHeader, Segmented } from "../ui";
import { Donut } from "../charts";
import { LotTable } from "./LotTable";
import { StockTable } from "./StockTable";
import type { TabContext } from "./PortfolioTabs";

export type HoldingsView = "stock" | "lot";

const VIEWS: { value: HoldingsView; label: string }[] = [
  { value: "stock", label: "By stock" },
  { value: "lot", label: "By lot" },
];

/** The holdings, either one line for each stock or one line for each purchase (a lot), and how they are spread. */
export function HoldingsTab({ data, showAccounts, onEdit, onRemove }: TabContext) {
  const [view, setView] = useState<HoldingsView>("stock");
  const toggle = <Segmented label="How to list holdings" size="sm" value={view} onChange={setView} options={VIEWS} />;
  const worth = data.positions
    .filter((p) => p.value !== undefined)
    .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
  return (
    <div className="grid gap-5 xl:grid-cols-3">
      {view === "stock" ? (
        <StockTable positions={data.positions} showAccounts={showAccounts} toggle={toggle} />
      ) : (
        <LotTable
          rows={data.holdings}
          showAccounts={showAccounts}
          toggle={toggle}
          onEdit={onEdit}
          onRemove={onRemove}
        />
      )}
      {view === "stock" && <Allocation worth={worth} />}
    </div>
  );
}

/** How the holdings are spread, one slice for each stock. It sits beside the by-stock list. */
function Allocation({ worth }: { worth: { symbol: string; value?: number }[] }) {
  return (
    <Card className="min-w-0">
      <CardHeader title="Allocation" subtitle="By current value" />
      <Donut slices={worth.map((p) => ({ label: p.symbol, value: p.value ?? 0 }))} />
      <p className="mt-5 text-[12.5px] text-ink-3">
        Valued at each stock's latest close in the market data. Dividends received are not included.
      </p>
    </Card>
  );
}
