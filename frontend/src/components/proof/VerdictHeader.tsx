import { dateTime } from "../../lib/format";
import type { StockProof } from "../../lib/proof";
import { ShariahBadge } from "../mode/ShariahBadge";
import { dataStatusSentence } from "../mode/words";

/** (a) The verdict, one plain sentence of why, and the data it rests on, right beside it. */
export function VerdictHeader({ proof }: { proof: StockProof }) {
  const asOf = proof.filing?.period_end ?? null;
  const status = {
    verdict: proof.verdict,
    data_status: proof.data_status,
    short: "",
    as_of: asOf,
  };
  return (
    <div className="space-y-2" role="group" aria-label="Verdict">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <ShariahBadge status={status} />
        <span aria-hidden className="text-[13px] font-medium text-ink-2">
          {dataStatusSentence(proof.data_status, asOf)}
        </span>
      </div>
      {proof.headline && <p className="text-[15px] font-semibold leading-snug text-ink">{proof.headline}</p>}
      {proof.data_notice && <p className="text-[13px] text-ink-2">{proof.data_notice}</p>}
      {(proof.screened_at || proof.methodology_version) && (
        <p className="text-[12px] text-ink-3">
          {proof.screened_at ? `Screened ${dateTime(proof.screened_at)}` : "Screened"}
          {proof.methodology_version ? `, using rules version ${proof.methodology_version}` : ""}.
        </p>
      )}
    </div>
  );
}
