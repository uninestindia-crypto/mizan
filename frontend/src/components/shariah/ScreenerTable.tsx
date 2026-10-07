import { CheckCircle2, HelpCircle, XCircle } from "lucide-react";
import { pct } from "../../lib/format";
import type { ShariahCompliance } from "../../lib/types";
import { Badge, Card, EmptyState, cx } from "../ui";
import { DataStatusBadge } from "./dataStatus";
import { STANDARD_LABEL, STANDARD_TONE, STATUS_LABEL, STATUS_TONE, type ScreenStatus } from "./labels";

const HEADERS = ["Symbol & Name", "Status", "AAOIFI", "TASIS", "Debt / M.Cap", "Cash & Equiv.", "Purification Ratio"];
const TH = "px-4 py-3";
const HEAD = "border-b border-line bg-surface-2 text-xs font-semibold uppercase tracking-wider text-ink-3";
const EMPTY_BODY = "Try adjusting your search query or compliance filter.";
const OPENER =
  "mt-1 rounded text-[12.5px] font-medium text-brand underline underline-offset-2 hover:text-brand-strong";

function StatusIcon({ status }: { status: ScreenStatus }) {
  if (status === "COMPLIANT") return <CheckCircle2 className="size-3" aria-hidden />;
  if (status === "QUESTIONABLE") return <HelpCircle className="size-3" aria-hidden />;
  return <XCircle className="size-3" aria-hidden />;
}

function Ratio({ value }: { value: number }) {
  const high = value > 0.33;
  const tone = high ? "text-down font-semibold" : "text-ink-2";
  return <span className={cx("num font-medium", tone)}>{pct(value, 1, false)}</span>;
}

function Row({ item, onOpen }: { item: ShariahCompliance; onOpen: (ticker: string, opener: HTMLElement) => void }) {
  return (
    <tr className="transition-colors hover:bg-surface-2/60">
      <td className="px-4 py-3">
        <div className="font-semibold text-ink">{item.symbol}</div>
        <div className="max-w-xs truncate text-xs text-ink-3">{item.company_name}</div>
        <button
          type="button"
          className={OPENER}
          aria-label={`How it was decided for ${item.company_name}`}
          onClick={(event) => onOpen(item.ticker, event.currentTarget)}
        >
          How it was decided
        </button>
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-col items-start gap-1">
          <Badge tone={STATUS_TONE[item.compliance_status]}>
            <StatusIcon status={item.compliance_status} /> {STATUS_LABEL[item.compliance_status]}
          </Badge>
          <DataStatusBadge status={item.data_status} />
        </div>
      </td>
      <td className="px-4 py-3 text-center">
        <Badge tone={STANDARD_TONE[item.aaoifi_status]}>{STANDARD_LABEL[item.aaoifi_status]}</Badge>
      </td>
      <td className="px-4 py-3 text-center">
        <Badge tone={STANDARD_TONE[item.tasis_status]}>{STANDARD_LABEL[item.tasis_status]}</Badge>
      </td>
      <td className="px-4 py-3 text-right">
        <Ratio value={item.debt_ratio} />
      </td>
      <td className="px-4 py-3 text-right">
        <Ratio value={item.cash_ratio} />
      </td>
      <td className="px-4 py-3 text-right">
        <span className="num font-mono text-ink-2">{pct(item.purification_ratio, 2, false)}</span>
      </td>
    </tr>
  );
}

export function ScreenerTable({
  items,
  onOpen,
}: {
  items: ShariahCompliance[];
  onOpen: (ticker: string, opener: HTMLElement) => void;
}) {
  return (
    <Card padded={false} className="overflow-hidden">
      <div className="overflow-x-auto" role="region" aria-label="Equities screener table" tabIndex={0}>
        <table className="w-full text-left text-sm">
          <thead className={HEAD}>
            <tr>
              {HEADERS.map((header, i) => (
                <th key={header} className={cx(TH, i >= 2 && i <= 3 && "text-center", i >= 4 && "text-right")}>
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {items.length === 0 ? (
              <tr>
                <td colSpan={HEADERS.length}>
                  <EmptyState title="No matching equities" body={EMPTY_BODY} />
                </td>
              </tr>
            ) : (
              items.map((item) => <Row key={item.ticker} item={item} onOpen={onOpen} />)
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
