import { Link } from "react-router";
import { inr } from "../../lib/format";
import {
  asOfLine,
  describeChange,
  hasPrice,
  type LiveLabel,
  type LiveQuote,
  type LiveQuotes,
  labelWords,
  NOT_CONNECTED_MESSAGE,
  quoteFor,
  useLiveQuotes,
} from "../../lib/live";
import { Badge, Button, cx } from "../ui";

// Read-only live prices. Every price carries a plain-word label; colour is never the only signal.

const LABEL_TONE: Record<LiveLabel, "brand" | "warn" | "neutral"> = {
  LIVE: "brand",
  DELAYED: "warn",
  LAST_CLOSE: "neutral",
  UNAVAILABLE: "neutral",
};

function LiveBadge({ label }: { label: LiveLabel }) {
  return (
    <Badge tone={LABEL_TONE[label]}>
      {label === "LIVE" && <span className="size-1.5 rounded-full bg-current" aria-hidden />}
      {labelWords(label)}
    </Badge>
  );
}

const CHANGE_COLOUR = { up: "text-up", down: "text-down", unchanged: "text-ink-2" } as const;

function ChangeText({ changePct }: { changePct: number | null }) {
  const change = describeChange(changePct);
  if (!change) return null;
  return (
    <span className={cx("num", CHANGE_COLOUR[change.word])}>
      {change.text} <span className="text-ink-3">{change.word}</span>
    </span>
  );
}

/** A quote with no price: the label "Not available" and, when the engine gave one, why. */
function Unavailable({ quote, large }: { quote: LiveQuote; large: boolean }) {
  const why = quote.message ?? (large ? "A live price is not available for this stock right now." : null);
  return (
    <>
      <LiveBadge label="UNAVAILABLE" />
      {why && <span className="text-ink-3">{why}</span>}
    </>
  );
}

function QuoteBody({ quote, large }: { quote: LiveQuote; large: boolean }) {
  if (!hasPrice(quote)) return <Unavailable quote={quote} large={large} />;
  const size = large ? "text-lg" : "text-[13px]";
  return (
    <>
      <LiveBadge label={quote.label} />
      <span className={cx("num font-semibold text-ink", size)}>{inr(quote.last_price)}</span>
      <ChangeText changePct={quote.change_pct} />
    </>
  );
}

const NOTE_CLASS = "flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[12.5px] text-ink-3";

/** Says once, with a button, how to turn live prices on. Nothing when they are connected or still loading. */
export function LiveConnectNote({ quotes, className }: { quotes: LiveQuotes | undefined; className?: string }) {
  if (!quotes || quotes.connected) return null;
  return (
    <div role="status" className={cx(NOTE_CLASS, className)}>
      <span>{quotes.message || NOT_CONNECTED_MESSAGE}</span>
      <Link to="/settings/accounts">
        <Button variant="secondary" size="sm">
          Open Accounts and keys
        </Button>
      </Link>
    </div>
  );
}

const CHIP_CLASS = "mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[12.5px]";

/** One small line for a list row, from prices fetched once for the whole list. Nothing until there is an answer. */
export function LiveChip({ symbol, quotes }: { symbol: string; quotes: LiveQuotes | undefined }) {
  const quote = quoteFor(quotes, symbol);
  if (!quote) return null;
  const line = asOfLine(quote);
  return (
    <span title={line ?? undefined} className={CHIP_CLASS}>
      <QuoteBody quote={quote} large={false} />
      {line && <span className="sr-only">{line}</span>}
    </span>
  );
}

/** A live price for one stock, asking the engine itself. For a list, fetch once and use LiveChip instead. */
export function LivePrice({ symbol }: { symbol: string }) {
  const live = useLiveQuotes([symbol]);
  if (live.data && !live.data.connected) return <LiveConnectNote quotes={live.data} />;
  const quote = quoteFor(live.data, symbol);
  if (!quote) return null;
  const line = asOfLine(quote);
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-sm">
        <QuoteBody quote={quote} large />
      </div>
      {line && <p className="text-[12px] text-ink-3">{line}</p>}
    </div>
  );
}
