import { ChevronDown } from "lucide-react";
import { useId, useState } from "react";
import type { ProofFigure, ProofInput, ProofTest } from "../../lib/proof";
import { cx } from "../ui";
import { countedWords, croreText, inputRole, readingsDiffer, rupeeText, sumText } from "./proofFormat";

function InputItem({ input, rupees }: { input: ProofInput; rupees: boolean }) {
  const counted = countedWords(input);
  return (
    <li className="space-y-0.5 rounded-lg border border-line bg-surface px-3 py-2">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <span className="font-medium text-ink">{input.label}</span>
        <span className="num font-semibold text-ink">
          {rupees ? rupeeText(input.value_inr) : croreText(input.value_cr)}
        </span>
      </div>
      <p className="text-[12px] text-ink-3">
        {inputRole(input)}
        {counted && ` · ${counted}`}
      </p>
      <p className="break-words text-[12px] text-ink-3">
        {input.xbrl_tag ? (
          <>
            Source field: <code className="rounded bg-surface-2 px-1 py-0.5 text-ink-2">{input.xbrl_tag}</code>
          </>
        ) : (
          "Hand-entered sample figure. No filing backs it."
        )}
      </p>
    </li>
  );
}

function Sums({ test }: { test: ProofTest }) {
  const readings: [string, ProofFigure | null][] = readingsDiffer(test)
    ? [
        ["Lower reading", test.low],
        ["Upper reading", test.high],
      ]
    : [["The sum", test.high ?? test.low]];
  return (
    <ul className="space-y-1 text-[12.5px] text-ink-2">
      {readings.map(([name, figure]) =>
        figure ? (
          <li key={name}>
            <span className="text-ink-3">{name}: </span>
            <span className="num">{sumText(figure)}</span>
          </li>
        ) : null,
      )}
    </ul>
  );
}

function inputKey(input: ProofInput, at: number): string {
  return `${input.label}-${at}`;
}

function FiguresBody({ test, id }: { test: ProofTest; id: string }) {
  const [rupees, setRupees] = useState(false);
  return (
    <div id={id} className="mt-2 space-y-3 text-[13px]">
      <Sums test={test} />
      <ul className="space-y-2">
        {test.inputs.map((input, at) => (
          <InputItem key={inputKey(input, at)} input={input} rupees={rupees} />
        ))}
      </ul>
      <button type="button" aria-pressed={rupees} onClick={() => setRupees(!rupees)} className={TOGGLE}>
        Show amounts in rupees
      </button>
    </div>
  );
}

const TOGGLE =
  "inline-flex min-h-10 items-center gap-1 rounded text-[13px] font-medium text-brand hover:underline md:min-h-0";

/** Every figure behind one test, so a person can check the sum against the filing. Closed until asked. */
export function FiguresExpander({ test }: { test: ProofTest }) {
  const [open, setOpen] = useState(false);
  const bodyId = useId();
  if (test.inputs.length === 0) return null;
  return (
    <div>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={bodyId}
        onClick={() => setOpen(!open)}
        className={TOGGLE}
      >
        <ChevronDown className={cx("size-4 transition-transform", open && "rotate-180")} aria-hidden />
        {open ? "Hide the figures" : "Show the figures"}
        <span className="sr-only"> for {test.title}</span>
      </button>
      {open && <FiguresBody test={test} id={bodyId} />}
    </div>
  );
}
