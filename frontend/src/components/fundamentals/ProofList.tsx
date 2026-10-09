import { date, inr } from "../../lib/format";
import type { FundamentalsProof } from "../../lib/fundamentalsTypes";
import { friendlyDates } from "../../lib/plainDates";
import { CopyFingerprint } from "../proof/CopyFingerprint";
import { FilingLink } from "./FilingLink";

/** A rupee amount in full for a filing figure, and with paise for a per-share figure. */
function amount(proof: FundamentalsProof): string {
  return proof.unit === "INR" ? inr(proof.value, 0) : inr(proof.value, 2);
}

function FromFiling({ proof }: { proof: FundamentalsProof }) {
  return (
    <div className="space-y-1">
      <p className="text-ink">
        <span className="font-medium">{proof.label}:</span> <span className="num">{amount(proof)}</span>
      </p>
      <p className="text-ink-3">
        Filing tag <code className="rounded bg-surface-2 px-1 py-0.5 text-[12px] text-ink">{proof.tag}</code>,{" "}
        {friendlyDates(proof.period)}
        {proof.filed_on ? `, filed ${date(proof.filed_on)}` : ""}
      </p>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <FilingLink url={proof.filing_url}>Open the filing</FilingLink>
        {proof.sha256 && <CopyFingerprint hash={proof.sha256} />}
      </div>
    </div>
  );
}

function FromPrice({ proof }: { proof: FundamentalsProof }) {
  return (
    <div className="space-y-1">
      <p className="text-ink">
        <span className="font-medium">{proof.label}:</span> <span className="num">{amount(proof)}</span>
      </p>
      <p className="text-ink-3">{friendlyDates(proof.period)}, from QuantOS's own end-of-day prices</p>
    </div>
  );
}

function ProofItem({ proof }: { proof: FundamentalsProof }) {
  return (
    <li className="rounded-lg bg-surface-2 p-3">
      {proof.kind === "PRICE" ? <FromPrice proof={proof} /> : <FromFiling proof={proof} />}
    </li>
  );
}

/** The numbers a figure was worked out from, each with where to check it. */
export function ProofList({ inputs }: { inputs: FundamentalsProof[] }) {
  if (inputs.length === 0) return null;
  return (
    <ul aria-label="What this was worked out from" className="space-y-3 text-[13px]">
      {inputs.map((proof, at) => (
        <ProofItem key={`${proof.kind}-${proof.tag}-${at}`} proof={proof} />
      ))}
    </ul>
  );
}
