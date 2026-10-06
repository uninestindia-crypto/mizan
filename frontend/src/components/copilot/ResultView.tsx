import type { ReactNode } from "react";
import { Badge, Callout } from "../ui";
import { FactsShown } from "./FactsShown";
import { HalalPanel } from "./HalalPanel";
import { DissentCard, ModelReadingCard } from "./ModelReadingCard";
import { readingWords, type ResultView as ResultModel } from "./resultModel";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2.5">
      <h3 className="text-[14px] font-semibold text-ink">{title}</h3>
      {children}
    </section>
  );
}

function CountList({ counts }: { counts: ResultModel["counts"] }) {
  if (counts.length === 0) return null;
  return (
    <ul
      aria-label="How many models read it each way"
      className="flex flex-wrap gap-x-4 gap-y-1 text-[13.5px] text-ink-2"
    >
      {counts.map((row) => (
        <li key={row.reading}>
          {readingWords(row.reading)}: <span className="num font-medium text-ink">{row.count}</span>
        </li>
      ))}
    </ul>
  );
}

function Summary({ view }: { view: ResultModel }) {
  return (
    <div className="space-y-3">
      <p className="text-[16px] font-semibold leading-snug text-ink">{view.headline}</p>
      <div className="flex flex-wrap items-center gap-2">
        <Badge>{view.consensus}</Badge>
        {view.sharedReading && <Badge>Shared reading: {view.sharedReading}</Badge>}
      </div>
      <p className="text-[13.5px] text-ink-2">{view.answeredLine}</p>
      <CountList counts={view.counts} />
      {view.newsTones && <p className="text-[13px] text-ink-3">{view.newsTones}</p>}
    </div>
  );
}

function Models({ models }: { models: ResultModel["models"] }) {
  return (
    <Section title="Each model's own reading">
      <ul className="space-y-3">
        {models.map((model) => (
          <ModelReadingCard key={model.key} model={model} />
        ))}
      </ul>
    </Section>
  );
}

function Dissenters({ view }: { view: ResultModel }) {
  if (view.noDissent) {
    return <p className="text-[13.5px] text-ink-2">No model read the evidence differently from the others.</p>;
  }
  if (view.dissent.length === 0) return null;
  return (
    <Section title="Models that read it differently, and why">
      <ul className="space-y-3">
        {view.dissent.map((entry) => (
          <DissentCard key={entry.key} entry={entry} />
        ))}
      </ul>
    </Section>
  );
}

function Notes({ notes }: { notes: readonly string[] }) {
  if (notes.length === 0) return null;
  return (
    <Section title="Worth keeping in mind">
      <ul className="list-disc space-y-1 pl-5 text-[13.5px] text-ink-2">
        {notes.map((note, index) => (
          <li key={index}>{note}</li>
        ))}
      </ul>
    </Section>
  );
}

/**
 * A finished second opinion, in a fixed order: the headline and counts, each model's own reading, the dissenters,
 * every note, the disclosure (always shown in full), the screener's halal result, and what the models were shown.
 */
export function ResultView({ view }: { view: ResultModel }) {
  return (
    <div className="space-y-6">
      <Summary view={view} />
      <Models models={view.models} />
      <Dissenters view={view} />
      <Notes notes={view.notes} />
      <Callout tone="warn" title="What this is, and what it is not">
        {view.disclosure}
      </Callout>
      {view.halal && <HalalPanel halal={view.halal} />}
      <FactsShown facts={view.facts} />
    </div>
  );
}
