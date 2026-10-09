import { Link } from "react-router";
import type { ProofProblem as Problem } from "../../lib/proof";
import { Button, EmptyState } from "../ui";
import { ScreenNow } from "./ScreenNow";

const MISSING_BODY =
  "QuantOS can read the company's latest results filing from NSE now and screen it, or you can look at the stocks " +
  "that are already screened.";

function Missing({ symbol }: { symbol: string }) {
  const next = (
    <div className="flex flex-col items-center gap-3">
      <ScreenNow symbol={symbol} />
      <Link to="/shariah" className="text-[13px] font-medium text-brand hover:underline">
        Open the Shariah screener
      </Link>
    </div>
  );
  return (
    <EmptyState
      className="py-6"
      title="No Shariah screening is available for this stock yet"
      body={MISSING_BODY}
      action={next}
    />
  );
}

const WORDS = {
  offline: {
    title: "QuantOS could not reach its engine",
    body: "Close QuantOS and open it again from the Start menu, then come back to this stock.",
  },
  other: {
    title: "The Shariah screening could not be loaded",
    body: "Something went wrong while loading it. Try again in a moment.",
  },
} as const;

/** The proof could not be loaded. Says why in plain words and what to click next. */
export function ProofProblem({ problem, symbol, onRetry }: { problem: Problem; symbol: string; onRetry: () => void }) {
  if (problem === "missing") return <Missing symbol={symbol} />;
  const { title, body } = WORDS[problem];
  const retry = (
    <Button variant="secondary" onClick={onRetry} className="min-h-10 md:min-h-0">
      Try again
    </Button>
  );
  return <EmptyState className="py-6" title={title} body={body} action={retry} />;
}
