import { Scale } from "lucide-react";
import type { ReactNode } from "react";
import { inr } from "../../lib/format";
import type { ZakatCalculationResult } from "../../lib/types";
import { Badge, Callout, Card, CardHeader, EmptyState } from "../ui";

function Line({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between p-3.5">
      <span className="text-ink-3">{label}</span>
      {children}
    </div>
  );
}

function Breakdown({ data }: { data: ZakatCalculationResult }) {
  const year = data.method === "active" ? "Lunar Year" : "Solar Year";
  return (
    <div className="space-y-4">
      <div className="rounded-[var(--radius-card)] border border-line bg-surface-2 p-5 text-center">
        <div className="text-xs font-semibold uppercase tracking-wider text-ink-3">Total Zakat Due</div>
        <div className="num mt-1 text-3xl font-bold tracking-tight text-brand">{inr(data.zakat_due)}</div>
        <div className="num mt-1 text-xs text-ink-3">
          Rate: {data.rate_pct}% ({year})
        </div>
      </div>
      <div className="divide-y divide-line rounded-[var(--radius-control)] border border-line bg-surface text-sm">
        <Line label="Zakatable Base:">
          <span className="num font-semibold text-ink">{inr(data.zakatable_base)}</span>
        </Line>
        <Line label="Silver Nisab Threshold:">
          <span className="num font-semibold text-ink">{inr(data.nisab_threshold)}</span>
        </Line>
        <Line label="Zakat Obligatory:">
          <Badge tone={data.is_obligatory ? "up" : "neutral"}>
            {data.is_obligatory ? "Yes (Above Nisab)" : "No (Exempt)"}
          </Badge>
        </Line>
      </div>
      <Callout tone="info" title="Scholarly Rule Citation">
        {data.method_notes}
      </Callout>
    </div>
  );
}

export function ZakatResult({ data }: { data: ZakatCalculationResult | undefined }) {
  return (
    <Card>
      <CardHeader title="Calculation Breakdown" subtitle="Audit assessment and Nisab threshold status." />
      {data ? (
        <Breakdown data={data} />
      ) : (
        <EmptyState
          title="No assessment calculated yet"
          body="Enter your total portfolio market value and select a method to evaluate Silver Nisab obligations."
          art={<Scale className="size-8 text-ink-3" />}
        />
      )}
    </Card>
  );
}
