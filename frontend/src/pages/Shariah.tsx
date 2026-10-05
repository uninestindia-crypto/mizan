import {
  BookOpen,
  CheckCircle2,
  Coins,
  Download,
  Layers,
  Scale,
  Search,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, CardHeader, Callout, Field, Input, cx } from "../components/ui";
import { inr, pct } from "../lib/format";
import {
  useShariahBaskets,
  useShariahComplianceSummary,
  useShariahStatus,
  useZakatCalculate,
} from "../lib/shariah";
import type { ShariahCompliance, ShariahBasket, ZakatCalculationResult } from "../lib/types";

type ShariahTab = "screener" | "baskets" | "purification" | "zakat" | "academy";

export default function Shariah() {
  const [tab, setTab] = useState<ShariahTab>("screener");
  const status = useShariahStatus();
  const summary = useShariahComplianceSummary();
  const baskets = useShariahBaskets();

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-6 py-8">
      {/* Hero Header */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex size-7 items-center justify-center rounded-lg bg-emerald-600/15 text-emerald-500">
              <Scale className="size-4" />
            </span>
            <span className="text-[13px] font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
              Mizan Ethical Engine
            </span>
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink sm:text-3xl">
            Shariah Wealth & Compliance
          </h1>
          <p className="mt-1 text-[14px] text-ink-2">
            Dual-standard (AAOIFI & TASIS) equity screening, thematic halal baskets, dividend purification, and zakat calculation.
          </p>
        </div>

        {status.data && (
          <div className="flex items-center gap-2 rounded-xl border border-line bg-surface p-3 text-[13px]">
            <span className="size-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-ink-2 font-medium">
              {status.data.companies_seeded} Audited Equities
            </span>
            <Badge tone="up" className="text-emerald-700 dark:text-emerald-300">
              Live WAL + DuckDB
            </Badge>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-line">
        {[
          { id: "screener", label: "Equities Screener", icon: ShieldCheck },
          { id: "baskets", label: "Thematic Baskets", icon: Layers },
          { id: "purification", label: "Dividend Purification", icon: Coins },
          { id: "zakat", label: "Equity Zakat", icon: Scale },
          { id: "academy", label: "Academy & Demat Guide", icon: BookOpen },
        ].map((t) => {
          const Icon = t.icon;
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id as ShariahTab)}
              className={cx(
                "flex items-center gap-2 border-b-2 px-4 py-3 text-[13.5px] font-medium transition-colors",
                active
                  ? "border-emerald-600 text-emerald-600 dark:border-emerald-400 dark:text-emerald-400"
                  : "border-transparent text-ink-3 hover:text-ink"
              )}
            >
              <Icon className="size-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Tab Panels */}
      {tab === "screener" && <ScreenerTab summary={summary.data ?? []} />}
      {tab === "baskets" && <BasketsTab baskets={baskets.data ?? []} />}
      {tab === "purification" && <PurificationTab />}
      {tab === "zakat" && <ZakatTab />}
      {tab === "academy" && <AcademyTab />}
    </div>
  );
}

function ScreenerTab({ summary }: { summary: ShariahCompliance[] }) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"ALL" | "COMPLIANT" | "NON_COMPLIANT">("ALL");

  const filtered = summary.filter((item) => {
    const matchesQ =
      item.symbol.toLowerCase().includes(query.toLowerCase()) ||
      item.company_name.toLowerCase().includes(query.toLowerCase());
    if (filter === "COMPLIANT") return matchesQ && item.is_compliant;
    if (filter === "NON_COMPLIANT") return matchesQ && !item.is_compliant;
    return matchesQ;
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-2.5 size-4 text-ink-3" />
          <input
            type="text"
            placeholder="Search company or symbol..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full rounded-xl border border-line bg-surface py-2 pl-9 pr-3 text-[13.5px] text-ink placeholder:text-ink-3 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
          />
        </div>
        <div className="flex items-center gap-2">
          {(["ALL", "COMPLIANT", "NON_COMPLIANT"] as const).map((mode) => (
            <Button
              key={mode}
              size="sm"
              variant={filter === mode ? "primary" : "ghost"}
              onClick={() => setFilter(mode)}
            >
              {mode === "ALL" ? "All" : mode === "COMPLIANT" ? "Compliant Only" : "Non-Compliant"}
            </Button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-line bg-surface">
        <table className="w-full text-left text-[13px]">
          <thead className="border-b border-line bg-surface-2 text-ink-3">
            <tr>
              <th className="px-4 py-3 font-semibold">Symbol & Name</th>
              <th className="px-4 py-3 font-semibold">Status</th>
              <th className="px-4 py-3 font-semibold">AAOIFI</th>
              <th className="px-4 py-3 font-semibold">TASIS</th>
              <th className="px-4 py-3 font-semibold">Debt / M.Cap</th>
              <th className="px-4 py-3 font-semibold">Cash & Equiv.</th>
              <th className="px-4 py-3 font-semibold">Purification Ratio</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {filtered.map((item) => (
              <tr key={item.ticker} className="hover:bg-surface-2/50 transition-colors">
                <td className="px-4 py-3">
                  <div className="font-semibold text-ink">{item.symbol}</div>
                  <div className="text-[12px] text-ink-3 truncate max-w-xs">{item.company_name}</div>
                </td>
                <td className="px-4 py-3">
                  {item.is_compliant ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11.5px] font-medium text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2 className="size-3" /> Compliant
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/10 px-2 py-0.5 text-[11.5px] font-medium text-rose-600 dark:text-rose-400">
                      <XCircle className="size-3" /> Non-Compliant
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <Badge tone={item.aaoifi_compliant ? "up" : "neutral"}>
                    {item.aaoifi_compliant ? "Passed" : "Failed"}
                  </Badge>
                </td>
                <td className="px-4 py-3">
                  <Badge tone={item.tasis_compliant ? "up" : "neutral"}>
                    {item.tasis_compliant ? "Passed" : "Failed"}
                  </Badge>
                </td>
                <td className="px-4 py-3 text-ink-2">
                  <span className={item.debt_ratio > 0.33 ? "text-rose-500 font-semibold" : ""}>
                    {pct(item.debt_ratio, 1)}
                  </span>
                </td>
                <td className="px-4 py-3 text-ink-2">
                  <span className={item.cash_ratio > 0.33 ? "text-rose-500 font-semibold" : ""}>
                    {pct(item.cash_ratio, 1)}
                  </span>
                </td>
                <td className="px-4 py-3 text-ink-2 font-mono">
                  {pct(item.purification_ratio, 2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function BasketsTab({ baskets }: { baskets: ShariahBasket[] }) {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      {baskets.map((b) => (
        <Card key={b.id} className="flex flex-col justify-between">
          <div>
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[12px] font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">
                  {b.category}
                </span>
                <h3 className="mt-1 text-lg font-bold text-ink">{b.name}</h3>
              </div>
              <Badge tone="up">100% Shariah</Badge>
            </div>
            <p className="mt-2 text-[13px] leading-relaxed text-ink-2">{b.thesis}</p>

            <div className="mt-4 grid grid-cols-3 gap-2 rounded-xl bg-surface-2 p-3 text-center">
              <div>
                <div className="text-[11px] text-ink-3">Exp. CAGR</div>
                <div className="text-[14px] font-bold text-up">{pct(b.expected_cagr, 1)}</div>
              </div>
              <div>
                <div className="text-[11px] text-ink-3">Sharpe</div>
                <div className="text-[14px] font-bold text-ink">{b.expected_sharpe.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-[11px] text-ink-3">Div. Yield</div>
                <div className="text-[14px] font-bold text-ink">{pct(b.dividend_yield, 2)}</div>
              </div>
            </div>

            <div className="mt-4">
              <div className="text-[12px] font-semibold text-ink-3">Key Constituents</div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {b.constituents?.map((c) => (
                  <span
                    key={c.symbol}
                    className="inline-flex items-center gap-1 rounded-lg border border-line bg-surface px-2 py-1 text-[12px]"
                  >
                    <span className="font-semibold text-ink">{c.symbol}</span>
                    <span className="text-ink-3">({pct(c.weight, 0)})</span>
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-6 flex items-center justify-between border-t border-line pt-4">
            <span className="text-[12px] text-ink-3">Export to Zerodha, Upstox, Groww</span>
            <Button size="sm" variant="secondary" className="gap-1.5">
              <Download className="size-3.5" /> 1-Click Export
            </Button>
          </div>
        </Card>
      ))}
    </div>
  );
}

function ZakatTab() {
  const [val, setVal] = useState("500000");
  const [method, setMethod] = useState("TRADER_QUICK");
  const calc = useZakatCalculate();
  const data = calc.data as ZakatCalculationResult | undefined;

  const handleCalculate = () => {
    const num = parseFloat(val) || 0;
    calc.mutate({ portfolio_value: num, calculation_method: method });
  };

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader
          title="Equity Zakat Calculator"
          subtitle="Calibrated to the Indian Silver Nisab standard (₹53,550.00) with AAOIFI standards."
        />
        <div className="flex flex-col gap-4">
          <Field label="Portfolio Value (INR)" htmlFor="z-val">
            <Input
              id="z-val"
              prefix="₹"
              value={val}
              onChange={(e) => setVal(e.target.value.replace(/[^\d.]/g, ""))}
            />
          </Field>

          <Field label="Calculation Method" htmlFor="z-method">
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setMethod("TRADER_QUICK")}
                className={cx(
                  "rounded-xl border p-3 text-left text-[13px] transition-colors",
                  method === "TRADER_QUICK"
                    ? "border-emerald-500 bg-emerald-500/10 font-semibold text-emerald-600 dark:text-emerald-400"
                    : "border-line bg-surface text-ink-2"
                )}
              >
                <div>Active Trader (100%)</div>
                <div className="text-[11px] font-normal text-ink-3">Full portfolio Net Asset Value</div>
              </button>
              <button
                type="button"
                onClick={() => setMethod("INVESTOR_NET_WORKING_CAPITAL")}
                className={cx(
                  "rounded-xl border p-3 text-left text-[13px] transition-colors",
                  method === "INVESTOR_NET_WORKING_CAPITAL"
                    ? "border-emerald-500 bg-emerald-500/10 font-semibold text-emerald-600 dark:text-emerald-400"
                    : "border-line bg-surface text-ink-2"
                )}
              >
                <div>Long-term Investor</div>
                <div className="text-[11px] font-normal text-ink-3">Zakatable net working assets only</div>
              </button>
            </div>
          </Field>

          <Button
            size="lg"
            variant="primary"
            loading={calc.isPending}
            onClick={handleCalculate}
            className="mt-2"
          >
            Calculate Zakat Due
          </Button>
        </div>
      </Card>

      <Card>
        <CardHeader title="Calculation Breakdown" subtitle="Audit assessment and Nisab threshold status." />
        {data ? (
          <div className="flex flex-col gap-4">
            <div className="rounded-2xl bg-surface-2 p-5 text-center">
              <div className="text-[13px] text-ink-3">Total Zakat Due</div>
              <div className="mt-1 text-3xl font-extrabold text-emerald-600 dark:text-emerald-400">
                {inr(data.zakat_due)}
              </div>
              <div className="mt-1 text-[12px] text-ink-3">
                Rate: {data.rate_pct}% ({data.method === "active" ? "Lunar Year" : "Solar Year"})
              </div>
            </div>

            <div className="divide-y divide-line rounded-xl border border-line bg-surface text-[13px]">
              <div className="flex justify-between p-3">
                <span className="text-ink-3">Zakatable Base:</span>
                <span className="font-semibold text-ink">{inr(data.zakatable_base)}</span>
              </div>
              <div className="flex justify-between p-3">
                <span className="text-ink-3">Silver Nisab Threshold:</span>
                <span className="font-semibold text-ink">{inr(data.nisab_threshold)}</span>
              </div>
              <div className="flex justify-between p-3">
                <span className="text-ink-3">Zakat Obligatory:</span>
                <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                  {data.is_obligatory ? "Yes (Above Nisab)" : "No (Exempt)"}
                </span>
              </div>
            </div>

            <Callout tone="info" title="Scholarly Rule Citation">
              {data.method_notes}
            </Callout>
          </div>
        ) : (
          <div className="flex h-48 items-center justify-center text-[13px] text-ink-3">
            Enter portfolio value and click calculate to view assessment.
          </div>
        )}
      </Card>
    </div>
  );
}

function PurificationTab() {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <Card>
        <CardHeader
          title="Cryptographic Dividend Purification"
          subtitle="Calculate exact Rupee charity deductions from non-operating interest income."
        />
        <div className="flex flex-col gap-4 text-[13.5px] leading-relaxed text-ink-2">
          <p>
            When a Shariah-compliant company receives minor non-operating interest income from short-term bank balances
            (permitted under AAOIFI if &lt; 5%), this portion of your dividend must be purified by donating to charity without spiritual reward expectation.
          </p>
          <div className="rounded-xl border border-line bg-surface-2 p-4">
            <div className="font-semibold text-ink">Formula:</div>
            <div className="mt-1 font-mono text-[12.5px] text-ink">
              Purification Amount = Dividend Received × Purification Ratio
            </div>
          </div>
          <div className="rounded-xl border border-line bg-surface-2 p-4">
            <div className="font-semibold text-ink">SHA-256 Chained Audit Trail:</div>
            <div className="mt-1 text-[12.5px] text-ink-3">
              Every calculated deduction is written into a tamper-evident sequential hash ledger (<span className="font-mono">hash = sha256(prev_hash | entry)</span>) ensuring institutional auditability.
            </div>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Purification History & Ledger" subtitle="Immutable audit receipts." />
        <div className="flex h-48 flex-col items-center justify-center gap-2 text-center text-[13px] text-ink-3">
          <Coins className="size-8 text-ink-3/50" />
          <div>No dividends registered for purification yet.</div>
          <div className="text-[12px]">Dividend entries from your holdings or paper books will appear here.</div>
        </div>
      </Card>
    </div>
  );
}

function AcademyTab() {
  return (
    <div className="grid gap-6 md:grid-cols-3">
      <Card>
        <CardHeader title="1. Rationale & Permissibility" subtitle="Foundational Fiqh" />
        <p className="text-[13px] leading-relaxed text-ink-2">
          Shares represent fractional ownership in real commercial assets (Musharakah). Holding equities is fundamentally halal, provided the core business and financial ratios adhere to ethical bounds.
        </p>
      </Card>
      <Card>
        <CardHeader title="2. Zero-Interest Demat Guide" subtitle="Broker Setup" />
        <p className="text-[13px] leading-relaxed text-ink-2">
          Step-by-step instructions for opening a cash-only, zero-margin Demat and trading account with Zerodha, Upstox, or Groww without signing interest-bearing credit agreements.
        </p>
      </Card>
      <Card>
        <CardHeader title="3. Beating Inflation Halal" subtitle="Wealth Preservation" />
        <p className="text-[13px] leading-relaxed text-ink-2">
          Keeping cash in savings accounts causes wealth erosion due to inflation. Disciplined equity investment protects family capital while upholding ethical and spiritual obligations.
        </p>
      </Card>
    </div>
  );
}
