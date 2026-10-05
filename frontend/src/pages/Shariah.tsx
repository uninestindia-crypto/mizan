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
import {
  Badge,
  Button,
  Callout,
  Card,
  CardHeader,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Segmented,
  cx,
} from "../components/ui";
import { inr, int, pct } from "../lib/format";
import {
  useShariahBaskets,
  useShariahComplianceSummary,
  useShariahStatus,
  useZakatCalculate,
} from "../lib/shariah";
import type { ShariahBasket, ShariahCompliance, ZakatCalculationResult } from "../lib/types";

type ShariahTab = "screener" | "baskets" | "purification" | "zakat" | "academy";

const clean = (value: string) => value.replace(/[^\d.]/g, "");

export default function Shariah() {
  const [tab, setTab] = useState<ShariahTab>("screener");
  const status = useShariahStatus();
  const summary = useShariahComplianceSummary();
  const baskets = useShariahBaskets();

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Ethical Wealth & Compliance"
        title="Mizan Shariah"
        subtitle="Dual-standard (AAOIFI & TASIS) equity screening, thematic halal baskets, dividend purification, and zakat calculation."
        actions={
          status.data ? (
            <div className="flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5 text-[13px] shadow-sm">
              <span className="size-2 rounded-full bg-up animate-pulse" />
              <span className="num font-medium text-ink-2">
                {int(status.data.companies_seeded)} Audited Equities
              </span>
              <Badge tone="up">Live WAL + DuckDB</Badge>
            </div>
          ) : undefined
        }
      />

      {/* Unified sub-navigation tab bar */}
      <nav aria-label="Shariah modules" className="flex gap-1 border-b border-line overflow-x-auto">
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
              type="button"
              onClick={() => setTab(t.id as ShariahTab)}
              className={cx(
                "-mb-px flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors whitespace-nowrap",
                active
                  ? "border-brand text-ink"
                  : "border-transparent text-ink-3 hover:text-ink"
              )}
            >
              <Icon className="size-4" />
              {t.label}
            </button>
          );
        })}
      </nav>

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
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented<"ALL" | "COMPLIANT" | "NON_COMPLIANT">
          label="Compliance filter"
          value={filter}
          onChange={setFilter}
          options={[
            { value: "ALL", label: "All Equities" },
            { value: "COMPLIANT", label: "Compliant Only" },
            { value: "NON_COMPLIANT", label: "Non-Compliant" },
          ]}
        />
        <div className="relative w-full sm:w-72">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-3"
            aria-hidden
          />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search company or symbol..."
            aria-label="Search company or symbol"
            className="h-10 w-full rounded-[var(--radius-control)] border border-line bg-surface pl-9 pr-3 text-sm text-ink placeholder:text-ink-3 focus:border-brand focus:outline-none focus:ring-3 focus:ring-brand/15"
          />
        </div>
      </div>

      <Card padded={false} className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-line bg-surface-2 text-xs font-semibold uppercase tracking-wider text-ink-3">
              <tr>
                <th className="px-4 py-3">Symbol & Name</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-center">AAOIFI</th>
                <th className="px-4 py-3 text-center">TASIS</th>
                <th className="px-4 py-3 text-right">Debt / M.Cap</th>
                <th className="px-4 py-3 text-right">Cash & Equiv.</th>
                <th className="px-4 py-3 text-right">Purification Ratio</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <EmptyState
                      title="No matching equities"
                      body="Try adjusting your search query or compliance filter."
                      art={<Search className="size-8 text-ink-3" />}
                    />
                  </td>
                </tr>
              ) : (
                filtered.map((item) => (
                  <tr key={item.ticker} className="hover:bg-surface-2/60 transition-colors">
                    <td className="px-4 py-3">
                      <div className="font-semibold text-ink">{item.symbol}</div>
                      <div className="text-xs text-ink-3 truncate max-w-xs">{item.company_name}</div>
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone={item.is_compliant ? "up" : "down"}>
                        {item.is_compliant ? (
                          <>
                            <CheckCircle2 className="size-3" /> Compliant
                          </>
                        ) : (
                          <>
                            <XCircle className="size-3" /> Non-Compliant
                          </>
                        )}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <Badge tone={item.aaoifi_compliant ? "up" : "neutral"}>
                        {item.aaoifi_compliant ? "Passed" : "Failed"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <Badge tone={item.tasis_compliant ? "up" : "neutral"}>
                        {item.tasis_compliant ? "Passed" : "Failed"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className={cx("num font-medium", item.debt_ratio > 0.33 ? "text-down font-semibold" : "text-ink-2")}>
                        {pct(item.debt_ratio, 1)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className={cx("num font-medium", item.cash_ratio > 0.33 ? "text-down font-semibold" : "text-ink-2")}>
                        {pct(item.cash_ratio, 1)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="num font-mono text-ink-2">
                        {pct(item.purification_ratio, 2)}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
      <p className="text-[12.5px] text-ink-3">
        {int(filtered.length)} of {int(summary.length)} equities shown. Audited daily per AAOIFI Standard No. 21 and TASIS benchmark thresholds.
      </p>
    </div>
  );
}

function BasketsTab({ baskets }: { baskets: ShariahBasket[] }) {
  return (
    <div className="grid gap-5 md:grid-cols-2">
      {baskets.map((b) => (
        <Card key={b.id} className="flex flex-col justify-between">
          <div>
            <CardHeader
              title={b.name}
              subtitle={b.category}
              action={<Badge tone="up">100% Shariah</Badge>}
            />
            <p className="text-[13.5px] leading-relaxed text-ink-2">{b.thesis}</p>

            <div className="mt-4 grid grid-cols-3 gap-2 rounded-[var(--radius-control)] border border-line bg-surface-2 p-3 text-center">
              <div>
                <div className="text-[11.5px] font-medium text-ink-3">Exp. CAGR</div>
                <div className="num mt-0.5 text-base font-bold text-up">{pct(b.expected_cagr, 1)}</div>
              </div>
              <div>
                <div className="text-[11.5px] font-medium text-ink-3">Sharpe</div>
                <div className="num mt-0.5 text-base font-bold text-ink">{b.expected_sharpe.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-[11.5px] font-medium text-ink-3">Div. Yield</div>
                <div className="num mt-0.5 text-base font-bold text-ink">{pct(b.dividend_yield, 2)}</div>
              </div>
            </div>

            <div className="mt-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-ink-3">Key Constituents</div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {b.constituents?.map((c) => (
                  <span
                    key={c.symbol}
                    className="inline-flex items-center gap-1 rounded-[var(--radius-control)] border border-line bg-surface px-2.5 py-1 text-xs"
                  >
                    <span className="font-semibold text-ink">{c.symbol}</span>
                    <span className="num text-ink-3">({pct(c.weight, 0)})</span>
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
            <span className="text-xs text-ink-3">Export order sheet for Zerodha, Upstox, Groww</span>
            <Button size="sm" variant="secondary" icon={<Download className="size-3.5" />}>
              1-Click Export
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
    <div className="grid gap-5 lg:grid-cols-2">
      <Card>
        <CardHeader
          title="Equity Zakat Calculator"
          subtitle="Calibrated to the Indian Silver Nisab standard (₹53,550.00) with AAOIFI standards."
        />
        <div className="space-y-4">
          <Field label="Portfolio Value (INR)" htmlFor="z-val">
            <Input
              id="z-val"
              prefix="₹"
              inputMode="decimal"
              value={val}
              onChange={(e) => setVal(clean(e.target.value))}
            />
          </Field>

          <Field label="Calculation Method" htmlFor="z-method">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <button
                type="button"
                onClick={() => setMethod("TRADER_QUICK")}
                className={cx(
                  "rounded-[var(--radius-control)] border p-3.5 text-left transition-colors",
                  method === "TRADER_QUICK"
                    ? "border-brand bg-brand-soft ring-1 ring-brand text-ink"
                    : "border-line bg-surface text-ink-2 hover:border-line-strong hover:bg-surface-2"
                )}
              >
                <div className="font-semibold text-sm text-ink">Active Trader (100%)</div>
                <div className="mt-0.5 text-xs text-ink-3">Full portfolio Net Asset Value (Lunar year)</div>
              </button>
              <button
                type="button"
                onClick={() => setMethod("INVESTOR_NET_WORKING_CAPITAL")}
                className={cx(
                  "rounded-[var(--radius-control)] border p-3.5 text-left transition-colors",
                  method === "INVESTOR_NET_WORKING_CAPITAL"
                    ? "border-brand bg-brand-soft ring-1 ring-brand text-ink"
                    : "border-line bg-surface text-ink-2 hover:border-line-strong hover:bg-surface-2"
                )}
              >
                <div className="font-semibold text-sm text-ink">Long-term Investor</div>
                <div className="mt-0.5 text-xs text-ink-3">Zakatable net working assets only (~25-30%)</div>
              </button>
            </div>
          </Field>

          <Button
            size="md"
            variant="primary"
            loading={calc.isPending}
            onClick={handleCalculate}
            className="w-full mt-2"
          >
            Calculate Zakat Due
          </Button>
        </div>
      </Card>

      <Card>
        <CardHeader title="Calculation Breakdown" subtitle="Audit assessment and Nisab threshold status." />
        {data ? (
          <div className="space-y-4">
            <div className="rounded-[var(--radius-card)] border border-line bg-surface-2 p-5 text-center">
              <div className="text-xs font-semibold uppercase tracking-wider text-ink-3">Total Zakat Due</div>
              <div className="num mt-1 text-3xl font-bold tracking-tight text-brand">
                {inr(data.zakat_due)}
              </div>
              <div className="num mt-1 text-xs text-ink-3">
                Rate: {data.rate_pct}% ({data.method === "active" ? "Lunar Year" : "Solar Year"})
              </div>
            </div>

            <div className="divide-y divide-line rounded-[var(--radius-control)] border border-line bg-surface text-sm">
              <div className="flex items-center justify-between p-3.5">
                <span className="text-ink-3">Zakatable Base:</span>
                <span className="num font-semibold text-ink">{inr(data.zakatable_base)}</span>
              </div>
              <div className="flex items-center justify-between p-3.5">
                <span className="text-ink-3">Silver Nisab Threshold:</span>
                <span className="num font-semibold text-ink">{inr(data.nisab_threshold)}</span>
              </div>
              <div className="flex items-center justify-between p-3.5">
                <span className="text-ink-3">Zakat Obligatory:</span>
                <Badge tone={data.is_obligatory ? "up" : "neutral"}>
                  {data.is_obligatory ? "Yes (Above Nisab)" : "No (Exempt)"}
                </Badge>
              </div>
            </div>

            <Callout tone="info" title="Scholarly Rule Citation">
              {data.method_notes}
            </Callout>
          </div>
        ) : (
          <EmptyState
            title="No assessment calculated yet"
            body="Enter your total portfolio market value and select a method to evaluate Silver Nisab obligations."
            art={<Scale className="size-8 text-ink-3" />}
          />
        )}
      </Card>
    </div>
  );
}

function PurificationTab() {
  return (
    <div className="grid gap-5 md:grid-cols-2">
      <Card>
        <CardHeader
          title="Cryptographic Dividend Purification"
          subtitle="Calculate exact Rupee charity deductions from non-operating interest income."
        />
        <div className="space-y-4 text-[13.5px] leading-relaxed text-ink-2">
          <p>
            When a Shariah-compliant company receives minor non-operating interest income from short-term bank balances
            (permitted under AAOIFI Standard No. 21 if &lt; 5%), this portion of your dividend must be purified by donating to charity without spiritual reward expectation.
          </p>
          <div className="rounded-[var(--radius-control)] border border-line bg-surface-2 p-3.5">
            <div className="text-xs font-semibold uppercase tracking-wider text-ink-3">Standard Formula</div>
            <div className="num mt-1 text-sm font-semibold text-ink">
              Purification Amount = Dividend Received × Purification Ratio
            </div>
          </div>
          <div className="rounded-[var(--radius-control)] border border-line bg-surface-2 p-3.5">
            <div className="text-xs font-semibold uppercase tracking-wider text-ink-3">SHA-256 Chained Audit Trail</div>
            <p className="mt-1 text-xs leading-relaxed text-ink-3">
              Every calculated deduction is written into a tamper-evident sequential hash ledger (<span className="num font-mono">hash = sha256(prev_hash | entry)</span>) ensuring institutional auditability and compliance certifiability.
            </p>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Purification History & Ledger" subtitle="Immutable audit receipts." />
        <EmptyState
          title="No dividends registered yet"
          body="Dividend entries from your live holdings or paper trading books will automatically generate purification receipts here."
          art={<Coins className="size-8 text-ink-3" />}
        />
      </Card>
    </div>
  );
}

function AcademyTab() {
  return (
    <div className="grid gap-5 md:grid-cols-3">
      <Card>
        <CardHeader title="1. Rationale & Permissibility" subtitle="Foundational Fiqh" />
        <p className="text-[13.5px] leading-relaxed text-ink-2">
          Shares represent fractional ownership in real commercial assets (Musharakah). Holding equities is fundamentally halal, provided the core business and financial ratios adhere to ethical bounds.
        </p>
      </Card>
      <Card>
        <CardHeader title="2. Zero-Interest Demat Guide" subtitle="Broker Setup" />
        <p className="text-[13.5px] leading-relaxed text-ink-2">
          Step-by-step instructions for opening a cash-only, zero-margin Demat and trading account with Zerodha, Upstox, or Groww without signing interest-bearing credit agreements.
        </p>
      </Card>
      <Card>
        <CardHeader title="3. Beating Inflation Halal" subtitle="Wealth Preservation" />
        <p className="text-[13.5px] leading-relaxed text-ink-2">
          Keeping cash in savings accounts causes wealth erosion due to inflation. Disciplined equity investment protects family capital while upholding ethical and spiritual obligations.
        </p>
      </Card>
    </div>
  );
}
