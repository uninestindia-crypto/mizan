import type { ProofSector } from "../../lib/proof";
import { Badge } from "../ui";
import { ACTIVITY_RESULT, MATCHED_IN, ruleName } from "./proofFormat";

function Segments({ names }: { names: string[] }) {
  if (names.length === 0) return <p className="text-[13px] text-ink-3">The filing lists no business segments.</p>;
  return (
    <div className="space-y-1">
      <p className="text-[13px] text-ink-3">Business segments in the filing</p>
      <ul className="flex flex-wrap gap-1.5">
        {names.map((name) => (
          <li key={name} className="rounded-full border border-line bg-surface-2 px-2.5 py-0.5 text-[12.5px] text-ink">
            {name}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Match({ sector }: { sector: ProofSector }) {
  if (sector.status !== "FAIL") return null;
  const where = sector.matched_in ? ` in ${MATCHED_IN[sector.matched_in]}` : "";
  return (
    <p className="text-[13px] text-ink-2">
      {sector.rule && <span className="font-medium text-ink">Rule: {ruleName(sector.rule)}. </span>}
      {sector.matched_keyword && <>It matched the word “{sector.matched_keyword}”{where}. </>}
      {sector.reason && <span>{sector.reason}.</span>}
    </p>
  );
}

function Row({ name, value }: { name: string; value: string | null }) {
  if (!value) return null;
  return (
    <>
      <dt className="text-ink-3">{name}</dt>
      <dd className="text-ink">{value}</dd>
    </>
  );
}

function Details({ sector }: { sector: ProofSector }) {
  return (
    <>
      {sector.plain && <p className="text-[13px] text-ink">{sector.plain}</p>}
      <Match sector={sector} />
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[13px]">
        <Row name="Decided on" value={sector.basis} />
        <Row name="NSE industry group" value={sector.industry_group} />
      </dl>
      <Segments names={sector.segments} />
    </>
  );
}

/** (b) Whether the business itself passes, which rule, which word, and exactly what it was decided on. */
export function SectorBlock({ sector }: { sector: ProofSector | null }) {
  const look = sector ? ACTIVITY_RESULT[sector.status] : null;
  return (
    <section aria-labelledby="proof-business" className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <h3 id="proof-business" className="text-[14.5px] font-semibold text-ink">
          Business activity
        </h3>
        {look && (
          <Badge tone={look.tone} className="gap-1.5 px-2.5 text-[12.5px] font-semibold">
            <look.icon className="size-3.5" aria-hidden />
            {look.word}
          </Badge>
        )}
      </div>
      {sector ? <Details sector={sector} /> : <p className="text-[13px] text-ink-2">The business test was not run.</p>}
    </section>
  );
}
