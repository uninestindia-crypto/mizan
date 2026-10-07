import { ChevronDown, Scale } from "lucide-react";
import { type ReactNode, type RefObject, useEffect, useId, useRef, useState } from "react";
import { useLocation } from "react-router";
import { useAppMode } from "../../lib/mode";
import { proofProblem, useStockProof } from "../../lib/proof";
import { Card, cx, Skeleton } from "../ui";
import { ProofProblem } from "./ProofProblem";
import { ProofView } from "./ProofView";

function Body({ symbol }: { symbol: string }) {
  const proof = useStockProof(symbol);
  if (proof.isPending) {
    return (
      <div className="space-y-3" role="status">
        <Skeleton className="h-16" />
        <p className="text-[13px] text-ink-3">Loading the Shariah screening...</p>
      </div>
    );
  }
  if (proof.isError) {
    return <ProofProblem problem={proofProblem(proof.error)} symbol={symbol} onRetry={() => void proof.refetch()} />;
  }
  return <ProofView proof={proof.data} symbol={symbol.toUpperCase()} />;
}

const TITLE = "Shariah screening";
const SUBTITLE = "The real figures and proof behind this stock's Shariah result. A screening aid, not a fatwa.";

/** In Shariah mode: open, with its heading, at the top of the stock's page. */
function Open({ symbol }: { symbol: string }) {
  return (
    <Card as="section">
      <div id="shariah-proof" role="region" aria-labelledby="shariah-proof-title" className="scroll-mt-4">
        <div className="mb-4 flex items-start gap-2.5">
          <Scale className="mt-0.5 size-5 shrink-0 text-ink-3" aria-hidden />
          <div className="min-w-0">
            <h2 id="shariah-proof-title" className="text-[15px] font-semibold text-ink">
              {TITLE}
            </h2>
            <p className="mt-0.5 text-[13px] text-ink-3">{SUBTITLE}</p>
          </div>
        </div>
        <Body symbol={symbol} />
      </div>
    </Card>
  );
}

const FOLD =
  "flex min-h-12 w-full items-center justify-between gap-3 rounded-[var(--radius-card)] px-5 py-3 text-left";

function FoldButton({ open, bodyId, onToggle }: { open: boolean; bodyId: string; onToggle: () => void }) {
  return (
    <h2 className="text-[15px] font-semibold text-ink">
      <button type="button" aria-expanded={open} aria-controls={bodyId} onClick={onToggle} className={FOLD}>
        <span className="flex items-center gap-2.5">
          <Scale className="size-5 text-ink-3" aria-hidden />
          {TITLE}
        </span>
        <ChevronDown className={cx("size-5 shrink-0 text-ink-3 transition", open && "rotate-180")} aria-hidden />
      </button>
    </h2>
  );
}

/** Opens itself, and scrolls to itself, when a Shariah badge sent the person here. */
function useOpenWhenAsked(asked: boolean, box: RefObject<HTMLDivElement | null>) {
  const [open, setOpen] = useState(asked);
  useEffect(() => {
    if (!asked) return;
    setOpen(true);
    box.current?.scrollIntoView?.({ block: "start" });
  }, [asked, box]);
  return [open, setOpen] as const;
}

/** In Institutional mode: one folded line. It loads nothing until opened, and opens itself from a Shariah badge. */
function Folded({ symbol, asked }: { symbol: string; asked: boolean }) {
  const bodyId = useId();
  const box = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useOpenWhenAsked(asked, box);
  return (
    <Card as="section" padded={false}>
      <div id="shariah-proof" ref={box} className="scroll-mt-4">
        <FoldButton open={open} bodyId={bodyId} onToggle={() => setOpen(!open)} />
        {open && (
          <div id={bodyId} className="border-t border-line px-5 py-5">
            <p className="mb-4 text-[13px] text-ink-3">{SUBTITLE}</p>
            <Body symbol={symbol} />
          </div>
        )}
      </div>
    </Card>
  );
}

/**
 * The Shariah proof for one stock. In Shariah mode it is open at the top of the page, so the first thing a person reads
 * is why the stock is, or is not, compliant. In Institutional mode it is a folded "Shariah screening" line.
 */
export function StockProofPanel({ symbol }: { symbol: string }): ReactNode {
  const { isShariah } = useAppMode();
  const asked = useLocation().hash === "#shariah-proof";
  return isShariah ? <Open symbol={symbol} /> : <Folded symbol={symbol} asked={asked} />;
}
