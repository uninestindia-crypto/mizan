import type { FundamentalsScorecard, ScorecardFact } from "../../lib/fundamentalsTypes";
import { friendlyDates } from "../../lib/plainDates";
import { Badge } from "../ui";
import { countsText, factWords } from "./format";

function FactRow({ fact }: { fact: ScorecardFact }) {
  return (
    <li className="space-y-1 rounded-xl border border-line bg-surface p-3.5" data-fact-status={fact.status}>
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
        <Badge>{factWords(fact.status)}</Badge>
        <span className="min-w-0 text-[13.5px] text-ink">{friendlyDates(fact.sentence)}</span>
      </div>
      {fact.rule_of_thumb && <p className="text-[12.5px] text-ink-3">{fact.rule_of_thumb}</p>}
    </li>
  );
}

/**
 * The facts about a company set against rules of thumb. The line above them, and every sentence, is the engine's own.
 * Nothing is coloured as good or bad: each fact says in words whether it is inside or outside its rule of thumb.
 */
export function ScorecardView({ card }: { card: FundamentalsScorecard }) {
  return (
    <section aria-labelledby="fund-scorecard" className="space-y-3">
      <div>
        <h3 id="fund-scorecard" className="text-[14.5px] font-semibold text-ink">
          Facts against rules of thumb
        </h3>
        <p className="mt-0.5 text-[13px] text-ink-2">{card.header}</p>
        <p className="mt-1 text-[12.5px] text-ink-3">{countsText(card.counts)}</p>
      </div>
      <ul aria-label="Facts about this company" className="grid gap-2.5 lg:grid-cols-2">
        {card.facts.map((fact) => (
          <FactRow key={fact.key} fact={fact} />
        ))}
      </ul>
    </section>
  );
}
