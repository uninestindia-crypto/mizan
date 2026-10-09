import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import { overallStatus } from "../../lib/shariah";
import type { ShariahAudit } from "../../lib/types";
import { Badge, Button, Callout, Card, Spinner } from "../ui";
import { DataStatusBadge } from "./dataStatus";
import { STANDARD_LABEL, STANDARD_TONE, STATUS_LABEL, STATUS_TONE } from "./labels";
import { useShariahAudit } from "./useShariahAudit";
import { VerdictPanel } from "./VerdictPanel";

function Verdict({ audit }: { audit: ShariahAudit }) {
  const aaoifi = audit.aaoifi_evaluation.status;
  const tasis = audit.tasis_evaluation.status;
  const overall = overallStatus(aaoifi, tasis);
  return (
    <div role="group" aria-label="Verdict" className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={STATUS_TONE[overall]}>{STATUS_LABEL[overall]}</Badge>
        <DataStatusBadge status={audit.data_status} />
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[13px] text-ink-2">
        <span className="inline-flex items-center gap-1.5">
          AAOIFI <Badge tone={STANDARD_TONE[aaoifi]}>{STANDARD_LABEL[aaoifi]}</Badge>
        </span>
        <span className="inline-flex items-center gap-1.5">
          TASIS <Badge tone={STANDARD_TONE[tasis]}>{STANDARD_LABEL[tasis]}</Badge>
        </span>
      </div>
      {audit.divergence_noted && audit.divergence_explanation && (
        <p className="text-[13px] text-ink-2">{audit.divergence_explanation}</p>
      )}
    </div>
  );
}

function Loaded({ audit }: { audit: ShariahAudit }) {
  return (
    <div className="space-y-4">
      <Verdict audit={audit} />
      <VerdictPanel audit={audit} />
    </div>
  );
}

/** "TCS.NS" is the engine's name for a share; a person knows it as TCS. */
const plainSymbol = (ticker: string) => ticker.replace(/\.[A-Z]+$/, "");

/** One stock's result, opened from the screener's list. Focus lands on its heading so nobody has to look for it. */
export function StockResultCard({ ticker, onClose }: { ticker: string; onClose: () => void }) {
  const result = useShariahAudit(ticker);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
    heading.current?.scrollIntoView?.({ block: "nearest" });
  }, [ticker]);
  const audit = result.data;
  return (
    <Card>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 ref={heading} tabIndex={-1} className="break-words text-[15px] font-semibold text-ink outline-none">
            {audit ? `${audit.symbol}, ${audit.company_name}` : `Screening result for ${plainSymbol(ticker)}`}
          </h2>
          {audit && <p className="mt-0.5 text-[13px] text-ink-3">{audit.sector}</p>}
        </div>
        <Button size="sm" variant="ghost" icon={<X className="size-3.5" aria-hidden />} onClick={onClose}>
          Close
        </Button>
      </div>
      {result.isPending && <Spinner label="Loading the screening result" />}
      {result.isError && (
        <Callout tone="warn" title="This result could not be loaded">
          Click Close, then click the company again.
        </Callout>
      )}
      {audit && <Loaded audit={audit} />}
    </Card>
  );
}
