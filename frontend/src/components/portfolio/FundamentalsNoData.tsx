import { Link } from "react-router";
import { useCompanyFundamentals } from "../../lib/fundamentalsQueries";
import { Card, CardHeader } from "../ui";

/** How many of these holdings are asked why. The rest point to their own page, where the reason is shown. */
const LOOKUPS = 10;

function Reason({ symbol }: { symbol: string }) {
  const found = useCompanyFundamentals(symbol);
  if (found.isPending) return <span className="text-ink-3">Looking up why…</span>;
  if (found.isError) return <span className="text-ink-3">Open the stock to see why.</span>;
  return <span className="text-ink-2">{found.data.data_notice}</span>;
}

function Row({ symbol, asked }: { symbol: string; asked: boolean }) {
  return (
    <li className="space-y-0.5 text-[13.5px]">
      <Link to={`/stock/${symbol}`} className="font-semibold text-ink hover:underline">
        {symbol}
      </Link>
      <p>{asked ? <Reason symbol={symbol} /> : <span className="text-ink-3">Open the stock to see why.</span>}</p>
    </li>
  );
}

function Unpriced({ symbols }: { symbols: string[] }) {
  if (symbols.length === 0) return null;
  return (
    <p className="mt-4 text-[13px] text-ink-2">
      <span className="font-medium text-ink">No price in the market data, so no weight: </span>
      {symbols.join(", ")}.
    </p>
  );
}

function Rows({ symbols }: { symbols: string[] }) {
  return (
    <>
      <CardHeader
        title="Holdings with no filing data"
        subtitle="Open a stock to ask QuantOS to read its latest results from NSE."
      />
      <ul aria-label="Holdings with no filing data" className="space-y-3">
        {symbols.map((symbol, at) => (
          <Row key={symbol} symbol={symbol} asked={at < LOOKUPS} />
        ))}
      </ul>
    </>
  );
}

/** The holdings QuantOS holds no filing data for, each with the engine's reason, and a way to get the results. */
export function FundamentalsNoData({ symbols, unpriced }: { symbols: string[]; unpriced: string[] }) {
  if (symbols.length === 0 && unpriced.length === 0) return null;
  return (
    <Card>
      {symbols.length > 0 && <Rows symbols={symbols} />}
      <Unpriced symbols={unpriced} />
    </Card>
  );
}
