import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { Donut } from "../components/charts";
import { DataGate, Illustration } from "../components/common";
import { type HoldingDraft, HoldingDialog } from "../components/HoldingDialog";
import { Button, Callout, Card, CardHeader, Delta, Dialog, EmptyState, PageHeader, Skeleton, Stat } from "../components/ui";
import { date, inr, inrCompact, inrSigned, int, num, pct, tone } from "../lib/format";
import { useDeleteHolding, usePortfolio } from "../lib/queries";
import type { PortfolioRow } from "../lib/types";

export default function Portfolio() {
  const [dialog, setDialog] = useState<{ open: boolean; initial?: Partial<HoldingDraft> }>({ open: false });
  return (
    <>
      <PageHeader
        title="Portfolio"
        subtitle="What you own, valued at the latest close, with the charges you would pay to sell and a fair comparison with NIFTY."
        actions={
          <Button icon={<Plus className="size-4" aria-hidden />} onClick={() => setDialog({ open: true })}>
            Add holding
          </Button>
        }
      />
      <DataGate>
        <PortfolioContent onEdit={(initial) => setDialog({ open: true, initial })} onAdd={() => setDialog({ open: true })} />
      </DataGate>
      <HoldingDialog open={dialog.open} onOpenChange={(open) => setDialog({ open })} initial={dialog.initial} />
    </>
  );
}

function PortfolioContent({ onEdit, onAdd }: { onEdit: (initial: Partial<HoldingDraft>) => void; onAdd: () => void }) {
  const portfolio = usePortfolio();
  const remove = useDeleteHolding();
  const [deleting, setDeleting] = useState<PortfolioRow | null>(null);

  if (portfolio.isPending) return <Skeleton className="h-96" />;
  const data = portfolio.data;
  if (!data || data.holdings.length === 0) {
    return (
      <Card>
        <EmptyState
          art={<Illustration name="empty-portfolio" className="size-44" />}
          title="Track what you own"
          body="Add your holdings to see your real gain after costs, how concentrated you are, and whether you are beating NIFTY."
          action={<Button onClick={onAdd}>Add your first holding</Button>}
        />
      </Card>
    );
  }
  const totals = data.totals!;
  const valued = data.holdings.filter((h) => h.value !== undefined);
  const beat = data.nifty ? data.nifty.holdings_value - data.nifty.nifty_value : null;

  return (
    <div className="space-y-5">
      <Card>
        <div className="grid grid-cols-2 gap-6 lg:grid-cols-5">
          <Stat label="Current value" value={inrCompact(totals.value)} sub={`Invested ${inrCompact(totals.cost)}`} />
          <Stat label="Total gain" value={inrSigned(totals.pnl)} tone={tone(totals.pnl)} sub={pct(totals.pnl_pct)} />
          <Stat label="Today" value={inrSigned(totals.day_change)} tone={tone(totals.day_change)} />
          <Stat
            label="Charges to sell all"
            value={inr(totals.exit_charges, 0)}
            hint="STT, exchange, SEBI and GST plus your broker's charges from Settings, if you sold everything at the last close today."
          />
          <Stat
            label="Versus NIFTY"
            value={beat === null ? "—" : inrSigned(beat)}
            tone={tone(beat)}
            sub={data.nifty ? `Same money, same days · to ${date(data.nifty.compare_on)}` : "Needs NIFTY data after your buy dates"}
            hint="What your holdings are worth compared with putting the same money into NIFTYBEES on each buy date, both valued on the last day NIFTY data covers."
          />
        </div>
      </Card>

      {data.warnings.length > 0 && (
        <Callout tone="warn" title="Too much in one place">
          <ul className="list-disc space-y-0.5 pl-4">
            {data.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
          <p className="mt-1.5">A single stock that large can undo years of gains if something goes wrong with that company.</p>
        </Callout>
      )}

      <div className="grid gap-5 xl:grid-cols-3">
        <Card padded={false} className="xl:col-span-2">
          <div className="px-5 pt-5">
            <CardHeader title="Holdings" subtitle={`${int(data.holdings.length)} positions`} />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead>
                <tr className="border-y border-line bg-surface-2/60 text-[12px] font-semibold uppercase tracking-wide text-ink-3">
                  <th className="px-5 py-2.5 text-left">Stock</th>
                  <th className="px-3 py-2.5 text-right">Qty</th>
                  <th className="px-3 py-2.5 text-right">Avg price</th>
                  <th className="px-3 py-2.5 text-right">Last close</th>
                  <th className="px-3 py-2.5 text-right">Value</th>
                  <th className="px-3 py-2.5 text-right">Gain</th>
                  <th className="px-5 py-2.5 text-right">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {data.holdings.map((h) => (
                  <tr key={h.id} className="group">
                    <td className="px-5 py-3">
                      <Link to={`/stock/${h.symbol}`} className="font-semibold text-ink hover:underline">
                        {h.symbol}
                      </Link>
                      <div className="text-[12px] text-ink-3">
                        {h.error ?? `Bought ${date(h.buy_date)}`}
                        {h.note ? ` · ${h.note}` : ""}
                      </div>
                    </td>
                    <td className="num px-3 py-3 text-right text-ink-2">{int(h.quantity)}</td>
                    <td className="num px-3 py-3 text-right text-ink-2">{num(h.avg_price)}</td>
                    <td className="num px-3 py-3 text-right text-ink-2">{num(h.close)}</td>
                    <td className="num px-3 py-3 text-right font-medium text-ink">{inr(h.value, 0)}</td>
                    <td className="px-3 py-3 text-right">
                      <Delta value={h.pnl} strong>
                        {inrSigned(h.pnl)}
                      </Delta>
                      <div className="num text-[12px] text-ink-3">{pct(h.pnl_pct)}</div>
                    </td>
                    <td className="px-5 py-3 text-right">
                      <div className="flex justify-end gap-1 opacity-60 transition-opacity group-hover:opacity-100">
                        <button
                          type="button"
                          aria-label={`Edit ${h.symbol}`}
                          className="rounded-lg p-1.5 text-ink-3 hover:bg-surface-2 hover:text-ink"
                          onClick={() =>
                            onEdit({ id: h.id, symbol: h.symbol, quantity: String(h.quantity), avg_price: String(h.avg_price), buy_date: h.buy_date, note: h.note })
                          }
                        >
                          <Pencil className="size-4" aria-hidden />
                        </button>
                        <button type="button" aria-label={`Remove ${h.symbol}`} className="rounded-lg p-1.5 text-ink-3 hover:bg-down-soft hover:text-down" onClick={() => setDeleting(h)}>
                          <Trash2 className="size-4" aria-hidden />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card>
          <CardHeader title="Allocation" subtitle="By current value" />
          <Donut slices={[...valued].sort((a, b) => (b.value ?? 0) - (a.value ?? 0)).map((h) => ({ label: h.symbol, value: h.value ?? 0 }))} />
          <p className="mt-5 text-[12.5px] text-ink-3">Valued at each stock's latest close in the market data. Dividends received are not included.</p>
        </Card>
      </div>
      <Dialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={`Remove ${deleting?.symbol ?? ""}?`}
        description="This removes the holding from QuantOS only. Nothing is sold."
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleting(null)}>
              Keep
            </Button>
            <Button
              variant="danger"
              loading={remove.isPending}
              onClick={() => deleting && remove.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
            >
              Remove
            </Button>
          </>
        }
      >
        <span />
      </Dialog>
    </div>
  );
}
