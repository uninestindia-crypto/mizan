import { Coins } from "lucide-react";
import { Card, CardHeader, EmptyState } from "../ui";

const EMPTY_BODY =
  "Dividend entries from your live holdings or paper trading books will automatically generate purification " +
  "receipts here.";
const BOX = "rounded-[var(--radius-control)] border border-line bg-surface-2 p-3.5";
const BOX_TITLE = "text-xs font-semibold uppercase tracking-wider text-ink-3";

function HowItWorks() {
  return (
    <Card>
      <CardHeader
        title="Dividend purification"
        subtitle="Calculate exact Rupee charity deductions from non-operating interest income."
      />
      <div className="space-y-4 text-[13.5px] leading-relaxed text-ink-2">
        <p>
          When a Shariah-compliant company receives minor non-operating interest income from short-term bank balances
          (permitted under AAOIFI Standard No. 21 if &lt; 5%), this portion of your dividend must be purified by
          donating to charity without spiritual reward expectation.
        </p>
        <div className={BOX}>
          <div className={BOX_TITLE}>Standard Formula</div>
          <div className="num mt-1 text-sm font-semibold text-ink">
            Purification Amount = Dividend Received × Purification Ratio
          </div>
        </div>
        <div className={BOX}>
          <div className={BOX_TITLE}>Linked receipts</div>
          <p className="mt-1 text-xs leading-relaxed text-ink-3">
            Every calculated deduction is saved as a receipt that is linked to the one before it, so a change to an
            older receipt can be detected.
          </p>
        </div>
      </div>
    </Card>
  );
}

export function PurificationTab() {
  return (
    <div className="grid gap-5 md:grid-cols-2">
      <HowItWorks />
      <Card>
        <CardHeader title="Purification History & Ledger" subtitle="Receipts, each linked to the one before." />
        <EmptyState
          title="No dividends registered yet"
          body={EMPTY_BODY}
          art={<Coins className="size-8 text-ink-3" />}
        />
      </Card>
    </div>
  );
}
