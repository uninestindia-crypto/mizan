import { ArrowDown, ArrowUp, ChevronDown, ChevronUp, X } from "lucide-react";
import { useState } from "react";
import type { Candidate } from "../../lib/aiOrder";
import { type OrderEntry, showAppSetup, UNKNOWN_HINT } from "../../lib/aiSource";
import { thinkingWords } from "../../lib/thinking";
import { Badge, Button } from "../ui";
import { useTestAi } from "./AiSourceQueries";
import { AiSourceTest } from "./AiSourceTest";
import { ModelFields } from "./ModelFields";

const CHIPS = {
  ready: { text: "Ready", tone: "up" },
  unknown: { text: "Not checked yet", tone: "neutral" },
  signed_out: { text: "Not signed in", tone: "warn" },
  missing: { text: "Not set up", tone: "neutral" },
} as const;

interface Props {
  position: number;
  total: number;
  candidate: Candidate;
  entry: OrderEntry;
  onMove: (by: -1 | 1) => void;
  onPick: (model: string | null, thinking: string | null) => void;
  onRemove: () => void;
}

/** The model and thinking level of one AI, with a test that asks it exactly as it is set up. */
function Choices({ candidate, entry, onPick }: Props) {
  const run = useTestAi();
  return (
    <div className="space-y-3 border-t border-line/60 pt-3">
      <ModelFields id={candidate.id} chosen={entry} onPick={onPick} />
      <AiSourceTest run={run} target={entry} quiet />
    </div>
  );
}

function chosenWords(entry: OrderEntry): string {
  if (!entry.model && !entry.thinking) return "Automatic";
  return [entry.model, entry.thinking && thinkingWords(entry.thinking)].filter(Boolean).join(" · ");
}

/** One AI on the list: where it stands, its place, and (opened) the model and thinking level chosen for it. */
export function AiOrderRow(props: Props) {
  const { position, total, candidate, entry, onMove, onRemove } = props;
  const [open, setOpen] = useState(false);
  const chip = CHIPS[candidate.state];
  const chipText = candidate.kind === "api" && candidate.state === "ready" ? "Key saved" : chip.text;
  return (
    <li className="space-y-3 rounded-lg border border-line bg-surface px-3 py-2.5" data-ai={candidate.id}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-brand/10 text-[11px] font-bold text-brand">
            {position}
          </span>
          <span className="truncate text-[13.5px] font-medium text-ink">{candidate.name}</span>
          <Badge tone={chip.tone}>{chipText}</Badge>
        </div>
        <div className="flex items-center gap-1">
          {candidate.state === "signed_out" && (
            <Button
              size="sm"
              variant="secondary"
              aria-label={`Set up ${candidate.name}`}
              onClick={() => showAppSetup(candidate.setupName ?? candidate.name)}
            >
              Set up
            </Button>
          )}
          <Button size="sm" variant="ghost" className="size-7 p-0" disabled={position === 1} aria-label={`Move ${candidate.name} up`} onClick={() => onMove(-1)}>
            <ArrowUp className="size-3.5" aria-hidden />
          </Button>
          <Button size="sm" variant="ghost" className="size-7 p-0" disabled={position === total} aria-label={`Move ${candidate.name} down`} onClick={() => onMove(1)}>
            <ArrowDown className="size-3.5" aria-hidden />
          </Button>
          <Button size="sm" variant="ghost" className="size-7 p-0" aria-label={`Take ${candidate.name} off the list`} onClick={onRemove}>
            <X className="size-3.5" aria-hidden />
          </Button>
        </div>
      </div>
      {candidate.state === "unknown" && <p className="text-[12px] text-ink-3">{UNKNOWN_HINT}</p>}
      <button
        type="button"
        aria-expanded={open}
        aria-label={`Model and thinking for ${candidate.name}`}
        onClick={() => setOpen((before) => !before)}
        className="flex w-full items-center justify-between text-left text-[12px] text-ink-3 hover:text-ink"
      >
        <span>Model and thinking: {chosenWords(entry)}</span>
        {open ? <ChevronUp className="size-3.5" aria-hidden /> : <ChevronDown className="size-3.5" aria-hidden />}
      </button>
      {open && <Choices {...props} />}
    </li>
  );
}
