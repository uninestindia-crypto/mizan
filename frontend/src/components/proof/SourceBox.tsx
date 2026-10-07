import { CircleCheck, CircleX, ExternalLink } from "lucide-react";
import { date } from "../../lib/format";
import { type ProofCheck, type ProofFiling, safeNseUrl } from "../../lib/proof";
import { CopyFingerprint } from "./CopyFingerprint";

/** A link to NSE only when the address really is on NSE's own sites. Anything else is shown as text, never a link. */
function FilingLink({ url, children }: { url: string | null; children: string }) {
  if (!url) return null;
  const safe = safeNseUrl(url);
  if (!safe) {
    return (
      <span className="break-all text-ink-2">
        {children}: <span className="text-ink-3">{url}</span> (not a link, because it is not on NSE's site)
      </span>
    );
  }
  return (
    <a
      href={safe}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex min-h-10 items-center gap-1 font-medium text-brand hover:underline md:min-h-0"
    >
      {children}
      <ExternalLink className="size-3.5" aria-hidden />
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  );
}

function CheckLine({ check }: { check: ProofCheck }) {
  const Icon = check.ok ? CircleCheck : CircleX;
  const detail = check.detail ? `. ${check.detail}` : "";
  return (
    <li className="flex items-start gap-2 text-[13px] text-ink-2">
      <Icon className={`mt-0.5 size-4 shrink-0 ${check.ok ? "text-up" : "text-down"}`} aria-hidden />
      <span>
        <span className="font-medium text-ink">{check.ok ? "Passed" : "Did not pass"}: </span>
        {check.name}
        {detail}
      </span>
    </li>
  );
}

const ALL_ADD_UP = "The filing adds up against itself.";
const NOT_ALL_ADD_UP = "Some checks on the filing did not pass, so treat its figures with care.";

function Checks({ filing }: { filing: ProofFiling }) {
  const { ok, checks } = filing.tie_out;
  return (
    <div className="space-y-1.5">
      <p className="text-[13px] font-medium text-ink">{ok ? ALL_ADD_UP : NOT_ALL_ADD_UP}</p>
      <ul className="space-y-1">
        {checks.map((check, at) => (
          <CheckLine key={`${check.name}-${at}`} check={check} />
        ))}
      </ul>
    </div>
  );
}

function Facts({ filing }: { filing: ProofFiling }) {
  const kind = filing.consolidated === null ? null : filing.consolidated ? "Consolidated" : "Standalone";
  const audit = filing.audited === null ? null : filing.audited ? "audited" : "not audited";
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[13px]">
      <dt className="text-ink-3">Period</dt>
      <dd className="text-ink">{filing.period_label ?? date(filing.period_end)}</dd>
      <dt className="text-ink-3">Filed on</dt>
      <dd className="text-ink">{date(filing.filed_on)}</dd>
      {kind && (
        <>
          <dt className="text-ink-3">Statement</dt>
          <dd className="text-ink">{audit ? `${kind}, ${audit}` : kind}</dd>
        </>
      )}
      {filing.sha256 && (
        <>
          <dt className="text-ink-3">Fingerprint (SHA-256)</dt>
          <dd>
            <CopyFingerprint hash={filing.sha256} />
          </dd>
        </>
      )}
    </dl>
  );
}

/** (e) Where the figures come from, so anyone can open the filing and check. Nothing when no filing backs them. */
export function SourceBox({ filing }: { filing: ProofFiling | null }) {
  if (filing === null) return null;
  return (
    <section aria-labelledby="proof-source" className="space-y-3 rounded-xl border border-line bg-surface-2 p-4">
      <h3 id="proof-source" className="text-[14.5px] font-semibold text-ink">
        Where this comes from
      </h3>
      <Facts filing={filing} />
      <p className="text-[12.5px] text-ink-3">
        The fingerprint is the same for anyone who downloads the same filing, so you can check it was not changed.
      </p>
      <div className="flex flex-wrap gap-x-5 gap-y-1">
        <FilingLink url={filing.detail_url}>Open the filing on NSE</FilingLink>
        <FilingLink url={filing.source_url}>Download the filing file</FilingLink>
      </div>
      <Checks filing={filing} />
    </section>
  );
}
