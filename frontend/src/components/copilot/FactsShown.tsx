import type { FactSectionView, ResultView } from "./resultModel";

function FactSection({ section }: { section: FactSectionView }) {
  return (
    <div>
      <h4 className="text-[13px] font-medium text-ink [overflow-wrap:anywhere]">
        {section.title}
        {section.fromOutside && <span className="ml-2 text-[12px] font-normal text-ink-3">(from outside sources)</span>}
      </h4>
      <p className="mt-0.5 whitespace-pre-wrap [overflow-wrap:anywhere] text-[13px] text-ink-2">{section.summary}</p>
    </div>
  );
}

/** What the models were shown, folded away until the person wants to check it. */
export function FactsShown({ facts }: { facts: ResultView["facts"] }) {
  return (
    <details className="rounded-xl border border-line bg-surface px-4 py-3">
      <summary className="cursor-pointer select-none text-[13.5px] font-medium text-ink">
        What the models were shown
      </summary>
      <div className="mt-3 space-y-3">
        {facts.sections.map((section, index) => (
          <FactSection key={index} section={section} />
        ))}
        {facts.sections.length === 0 && <p className="text-[13px] text-ink-3">No facts were recorded for this run.</p>}
        {facts.unavailable.length > 0 && (
          <p className="text-[13px] text-ink-3">Not available right now: {facts.unavailable.join(", ")}.</p>
        )}
      </div>
    </details>
  );
}
