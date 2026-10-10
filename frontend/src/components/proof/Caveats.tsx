import type { StockProof } from "../../lib/proof";
import { Callout } from "../ui";
import { NOT_A_FATWA } from "./proofFormat";

function Lines({ lines, empty }: { lines: string[]; empty: string }) {
  if (lines.length === 0) return <p className="text-[13px] text-ink-3">{empty}</p>;
  return (
    <ul className="list-disc space-y-1 pl-5 text-[13px] text-ink-2">
      {lines.map((line) => (
        <li key={line}>{line}</li>
      ))}
    </ul>
  );
}

/** (f) What would change this and what this does not cover, always in full and never folded away. */
export function Caveats({ proof }: { proof: StockProof }) {
  return (
    <div className="space-y-4">
      <section aria-labelledby="proof-change" className="space-y-1.5">
        <h3 id="proof-change" className="text-[14.5px] font-semibold text-ink">
          What would change this
        </h3>
        <Lines lines={proof.what_would_change_it} empty="Nothing specific to report." />
      </section>
      <section aria-labelledby="proof-not-covered" className="space-y-1.5">
        <h3 id="proof-not-covered" className="text-[14.5px] font-semibold text-ink">
          What this does not cover
        </h3>
        <Lines lines={proof.not_covered} empty="No scholar has reviewed this result." />
        <p className="text-[13px] font-semibold text-ink">{NOT_A_FATWA}</p>
      </section>
    </div>
  );
}

/** (g) When the older hand-entered sample says something different, say so and say what. */
export function SampleComparison({ proof }: { proof: StockProof }) {
  const { differs, note } = proof.sample_comparison;
  if (!differs) return null;
  return (
    <Callout tone="warn" title="Different from QuantOS's older sample">
      {note ?? "The older hand-entered sample gave a different result for this stock."}
    </Callout>
  );
}
