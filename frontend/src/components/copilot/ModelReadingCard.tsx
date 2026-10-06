import { Badge } from "../ui";
import { readingWords } from "./resultModel";
import type { DissentView, ModelView } from "./resultModel";

function Points({ title, items }: { title: string; items: readonly string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h4 className="text-[12.5px] font-medium text-ink-3">{title}</h4>
      <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[13.5px] text-ink">
        {items.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function WhoAnswered({ name, modelName }: { name: string; modelName: string | null }) {
  return (
    <div className="min-w-0">
      <span className="font-semibold text-ink">{name}</span>
      {modelName && <span className="text-ink-3"> · {modelName}</span>}
    </div>
  );
}

/** One model's own reading with its reasons. A model that could not answer is shown too, with its reason. */
export function ModelReadingCard({ model }: { model: ModelView }) {
  return (
    <li className="space-y-3 rounded-xl border border-line bg-surface px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-[13.5px]">
        <WhoAnswered name={model.name} modelName={model.modelName} />
        {model.answered ? <Badge>{readingWords(model.reading)}</Badge> : <Badge tone="warn">Could not answer</Badge>}
      </div>
      {!model.answered && <p className="text-[13.5px] text-ink-2">{model.error}</p>}
      <Points title="Its reasons" items={model.reasons} />
      <Points title="Risks it pointed to" items={model.risks} />
      <Points title="What it said was missing" items={model.missing} />
      {[model.newsTone, model.stability, model.anchoring, model.informed, model.recheckProblem].map(
        (line, index) =>
          line && (
            <p key={index} className="text-[12.5px] text-ink-3">
              {line}
            </p>
          ),
      )}
    </li>
  );
}

/** A model that read the evidence differently from the rest, and why. */
export function DissentCard({ entry }: { entry: DissentView }) {
  return (
    <li className="space-y-3 rounded-xl border border-line bg-surface-2 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-[13.5px]">
        <WhoAnswered name={entry.name} modelName={entry.modelName} />
        <Badge>{readingWords(entry.reading)}</Badge>
      </div>
      <Points title="Its reasons" items={entry.reasons} />
      <Points title="Risks it pointed to" items={entry.risks} />
    </li>
  );
}
