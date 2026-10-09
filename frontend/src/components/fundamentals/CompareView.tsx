import { X } from "lucide-react";
import { errorMessage } from "../../lib/api";
import { COMPARE_MAX, COMPARE_MIN, useFundamentalsCompare } from "../../lib/fundamentalsQueries";
import type { CompareAnswer } from "../../lib/fundamentalsTypes";
import { SymbolSearch } from "../common";
import { Callout, Card, cx, Skeleton } from "../ui";
import { CompareTable } from "./CompareTable";
import { basisWords } from "./format";

const CHIP = "inline-flex items-center gap-1 rounded-full border border-line bg-surface-2 py-1 pl-3 pr-1";

function Chip({ symbol, onRemove }: { symbol: string; onRemove: () => void }) {
  return (
    <li className={CHIP}>
      <span className="text-[13px] font-semibold text-ink">{symbol}</span>
      <button
        type="button"
        aria-label={`Remove ${symbol}`}
        onClick={onRemove}
        className="rounded-full p-1.5 text-ink-3 hover:bg-surface-3 hover:text-ink"
      >
        <X className="size-3.5" aria-hidden />
      </button>
    </li>
  );
}

function Chosen({ symbols, onRemove }: { symbols: string[]; onRemove: (symbol: string) => void }) {
  if (symbols.length === 0) return null;
  return (
    <ul aria-label="Companies to compare" className="flex flex-wrap gap-2">
      {symbols.map((symbol) => (
        <Chip key={symbol} symbol={symbol} onRemove={() => onRemove(symbol)} />
      ))}
    </ul>
  );
}

function Choose(props: { symbols: string[]; onChange: (symbols: string[]) => void }) {
  const { symbols } = props;
  const full = symbols.length >= COMPARE_MAX;
  return (
    <div className="space-y-3">
      <p className="text-[13px] text-ink-2">
        Pick {COMPARE_MIN} to {COMPARE_MAX} companies. They are put side by side only where their figures are on the
        same basis.
      </p>
      <Chosen symbols={symbols} onRemove={(s) => props.onChange(symbols.filter((x) => x !== s))} />
      {full ? (
        <p className="text-[13px] text-ink-3">That is the most that can be compared at once.</p>
      ) : (
        <div className="max-w-md">
          <SymbolSearch
            onPick={(s) => props.onChange([...symbols, s])}
            exclude={symbols}
            placeholder="Search for a company to add"
          />
        </div>
      )}
    </div>
  );
}

function Outside({ answer }: { answer: CompareAnswer }) {
  const left = answer.companies.filter((c) => !c.included);
  if (left.length === 0) return null;
  return (
    <ul aria-label="Companies not in the lines" className="space-y-1 text-[13px] text-ink-2">
      {left.map((c) => (
        <li key={c.symbol}>
          <span className="font-medium text-ink">{c.symbol} is not in the lines below. </span>
          {c.reason}
        </li>
      ))}
    </ul>
  );
}

function Notes({ notes }: { notes: string[] }) {
  if (notes.length === 0) return null;
  return (
    <ul aria-label="Notes" className="list-disc space-y-0.5 pl-5 text-[13px] text-ink-2">
      {notes.map((note) => (
        <li key={note}>{note}</li>
      ))}
    </ul>
  );
}

function Result({ answer, busy }: { answer: CompareAnswer; busy: boolean }) {
  const basis = basisWords(answer.basis);
  return (
    <Card>
      <div aria-busy={busy} className={cx("space-y-4 transition-opacity", busy && "opacity-60")}>
        <p className="text-[14px] font-medium text-ink">{answer.statement}</p>
        {basis && <p className="text-[13px] text-ink-2">Compared on a {basis.toLowerCase()} basis.</p>}
        <Outside answer={answer} />
        <Notes notes={answer.notes} />
        <CompareTable answer={answer} />
      </div>
    </Card>
  );
}

/** Two to four companies side by side. Nothing is ranked: each figure is the company's own, with its date. */
export function CompareView(props: { symbols: string[]; onChange: (symbols: string[]) => void }) {
  const ready = props.symbols.length >= COMPARE_MIN;
  const found = useFundamentalsCompare(ready ? props.symbols : null);
  return (
    <div className="space-y-4">
      <Card>
        <Choose symbols={props.symbols} onChange={props.onChange} />
      </Card>
      {ready && found.isPending && <Skeleton className="h-48" />}
      {ready && found.isError && (
        <Callout tone="danger" title="The comparison could not be made">
          {errorMessage(found.error)}
        </Callout>
      )}
      {ready && found.data && <Result answer={found.data} busy={found.isPlaceholderData} />}
    </div>
  );
}
