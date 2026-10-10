import type { StockProof } from "../../lib/proof";
import { Caveats, SampleComparison } from "./Caveats";
import { ScreenNow } from "./ScreenNow";
import { SectorBlock } from "./SectorBlock";
import { SourceBox } from "./SourceBox";
import { StandardsBlock } from "./StandardsBlock";
import { VerdictHeader } from "./VerdictHeader";

/** Only a result read from a filing needs no further step; every other result can be refreshed from the filing. */
function needsFiling(proof: StockProof): boolean {
  return proof.data_status !== "VERIFIED_FILING";
}

/**
 * A stock that is not screened has no business result worth showing unless the business itself was ruled out: "passed"
 * beside "not screened" would read as a pass.
 */
function showsBusiness(proof: StockProof): boolean {
  return proof.verdict !== "NOT_SCREENED" || proof.sector?.status === "FAIL";
}

/** Everything the proof says, in the order a person reads it: verdict, business, tests, source, caveats. */
export function ProofView({ proof, symbol }: { proof: StockProof; symbol: string }) {
  return (
    <div className="space-y-6">
      <VerdictHeader proof={proof} />
      {needsFiling(proof) && <ScreenNow symbol={symbol} />}
      {showsBusiness(proof) && <SectorBlock sector={proof.sector} />}
      <StandardsBlock proof={proof} />
      <SourceBox filing={proof.filing} />
      <Caveats proof={proof} />
      <SampleComparison proof={proof} />
    </div>
  );
}
