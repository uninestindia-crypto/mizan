import type { ProofStandard, ProofTest, StockProof } from "../../lib/proof";
import { Badge } from "../ui";
import { FiguresExpander } from "./FiguresExpander";
import { LimitBar } from "./LimitBar";
import {
  DEPENDS_SENTENCE,
  limitPercent,
  percent,
  readingsDiffer,
  RESULT,
  SAYS_CANNOT_SAY,
  STANDARD_RESULT,
  TWO_READINGS_SENTENCE,
} from "./proofFormat";

function ResultWord({ test }: { test: ProofTest }) {
  const { word, tone, icon: Icon } = RESULT[test.result];
  return (
    <Badge tone={tone} className="gap-1.5 px-2.5 text-[12.5px] font-semibold">
      <Icon className="size-3.5" aria-hidden />
      {word}
    </Badge>
  );
}

function Readings({ test }: { test: ProofTest }) {
  if (test.low === null || test.high === null) return null;
  const both = readingsDiffer(test);
  return (
    <dl className="flex flex-wrap gap-x-6 gap-y-1 text-[13px]">
      <div>
        <dt className="text-ink-3">{both ? "Lower reading" : "Figure"}</dt>
        <dd className="num font-semibold text-ink">{percent(test.low.pct)}</dd>
      </div>
      {both && (
        <div>
          <dt className="text-ink-3">Upper reading</dt>
          <dd className="num font-semibold text-ink">{percent(test.high.pct)}</dd>
        </div>
      )}
      <div>
        <dt className="text-ink-3">Limit</dt>
        <dd className="num font-semibold text-ink">{limitPercent(test.limit_pct)}</dd>
      </div>
    </dl>
  );
}

/** The contract's sentence about a figure the filing does not itemise, unless the test's own words already say it. */
function ReadingsNote({ test }: { test: ProofTest }) {
  if (!readingsDiffer(test)) return null;
  if (test.result === "DEPENDS") {
    return test.plain.includes(SAYS_CANNOT_SAY) ? null : <p className="text-[13px] text-ink-2">{DEPENDS_SENTENCE}</p>;
  }
  return <p className="text-[13px] text-ink-2">{TWO_READINGS_SENTENCE}</p>;
}

function TestItem({ test }: { test: ProofTest }) {
  return (
    <li className="space-y-2 rounded-xl border border-line bg-surface px-3.5 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h5 className="min-w-0 text-[13.5px] font-semibold text-ink">{test.title}</h5>
        <ResultWord test={test} />
      </div>
      <Readings test={test} />
      <LimitBar test={test} />
      {test.plain && <p className="text-[13px] text-ink-2">{test.plain}</p>}
      <ReadingsNote test={test} />
      <FiguresExpander test={test} />
    </li>
  );
}

function StandardItem({ standard }: { standard: ProofStandard }) {
  const { word, tone, icon: Icon } = STANDARD_RESULT[standard.status];
  return (
    <section aria-label={`${standard.standard} tests`} className="min-w-0 space-y-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-[14px] font-semibold text-ink">{standard.standard}</h4>
        <Badge tone={tone} className="gap-1.5 px-2.5 text-[12.5px] font-semibold">
          <Icon className="size-3.5" aria-hidden />
          {word}
        </Badge>
      </div>
      {standard.summary && <p className="text-[13px] text-ink-2">{standard.summary}</p>}
      <ul className="space-y-2.5">
        {standard.tests.map((test) => (
          <TestItem key={test.key} test={test} />
        ))}
      </ul>
    </section>
  );
}

/** Why the two standards disagree, unless the headline above has already said it in the same words. */
function Divergence({ proof }: { proof: StockProof }) {
  const { noted, explanation } = proof.divergence;
  if (!noted || !explanation || proof.headline.includes(explanation)) return null;
  return <p className="rounded-lg bg-warn-soft px-3 py-2 text-[13px] text-ink">{explanation}</p>;
}

/** The four tests of each standard, side by side when there is room: what is measured, figure, limit, result. */
export function StandardsBlock({ proof }: { proof: StockProof }) {
  if (proof.standards.length === 0) return null;
  return (
    <section aria-labelledby="proof-standards" className="space-y-3">
      <h3 id="proof-standards" className="text-[14.5px] font-semibold text-ink">
        The four tests
      </h3>
      <Divergence proof={proof} />
      <div className="grid gap-5 lg:grid-cols-2">
        {proof.standards.map((standard) => (
          <StandardItem key={standard.standard} standard={standard} />
        ))}
      </div>
    </section>
  );
}
