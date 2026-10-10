import { Plus } from "lucide-react";
import { Link } from "react-router";
import {
  added,
  type Candidate,
  choose,
  move,
  orderView,
  without,
  withKept,
} from "../../lib/aiOrder";
import { type AiChoice, type AiSettingsPatch, type AiStatus, type OrderEntry, showAppSetup } from "../../lib/aiSource";
import { Badge, Button } from "../ui";
import { AiOrderRow } from "./AiOrderRow";

interface Props {
  status: AiStatus;
  choice: AiChoice;
  onChange: (patch: AiSettingsPatch) => void;
}

function Addable({ items, onAdd }: { items: Candidate[]; onAdd: (id: string) => void }) {
  if (items.length === 0) return null;
  return (
    <div className="space-y-1.5">
      <h5 className="text-[12px] font-semibold uppercase tracking-wider text-ink-3">Ready, but not on your list</h5>
      <ul className="space-y-1.5">
        {items.map((item) => (
          <li key={item.id} className="flex items-center justify-between rounded-lg border border-dashed border-line px-3 py-2">
            <span className="text-[13px] text-ink-2">{item.name}</span>
            <Button size="sm" variant="secondary" icon={<Plus className="size-3.5" aria-hidden />} aria-label={`Add ${item.name} to the list`} onClick={() => onAdd(item.id)}>
              Add
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function NotSetUp({ items }: { items: Candidate[] }) {
  if (items.length === 0) return null;
  return (
    <div className="space-y-1.5">
      <h5 className="text-[12px] font-semibold uppercase tracking-wider text-ink-3">Not set up yet</h5>
      <ul className="grid gap-1.5 sm:grid-cols-2">
        {items.map((item) => (
          <li key={item.id} className="flex items-center justify-between gap-2 rounded-lg border border-line px-3 py-2">
            <span className="flex min-w-0 items-center gap-2 text-[13px] text-ink-2">
              <span className="truncate">{item.name}</span>
              <Badge tone="neutral">{item.kind === "cli" ? "Not installed" : "No key yet"}</Badge>
            </span>
            {item.kind === "cli" ? (
              <Button size="sm" variant="secondary" aria-label={`Set up ${item.name}`} onClick={() => showAppSetup(item.setupName ?? item.name)}>
                Set up
              </Button>
            ) : (
              <Link to="/settings/accounts" aria-label={`Add a key for ${item.name}`} className="text-[12.5px] font-medium text-brand hover:underline">
                Add a key
              </Link>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * The AIs the Copilot asks, in the order it asks them, with the model and thinking level chosen for each. The apps on
 * this computer and the saved keys share one list. Any change saves the whole list at once.
 */
export function AiOrder({ status, choice, onChange }: Props) {
  const view = orderView(status, choice);
  const entries: OrderEntry[] = view.listed.map((item) => item.entry);
  const save = (next: OrderEntry[]) => onChange({ ai_order: withKept(next, status, choice) });
  return (
    <section aria-labelledby="ai-order-title" className="space-y-3">
      <div>
        <h4 id="ai-order-title" className="text-[13.5px] font-semibold text-ink">
          Your AIs, in the order they are asked
        </h4>
        <p className="mt-0.5 text-[12.5px] text-ink-3">
          The Copilot asks the first one. If it cannot answer, it asks the next. Open an AI to choose its model and how
          hard it thinks.
        </p>
      </div>
      {view.listed.length === 0 ? (
        <p className="rounded-lg border border-dashed border-line px-3 py-3 text-[13px] text-ink-3">
          No AI is on your list yet.
        </p>
      ) : (
        <ol className="space-y-2">
          {view.listed.map(({ candidate, entry }, index) => (
            <AiOrderRow
              key={candidate.id}
              position={index + 1}
              total={view.listed.length}
              candidate={candidate}
              entry={entry}
              onMove={(by) => save(move(entries, index, by))}
              onPick={(model, thinking) => save(choose(entries, candidate.id, model, thinking))}
              onRemove={() => save(without(entries, candidate.id))}
            />
          ))}
        </ol>
      )}
      <Addable items={view.addable} onAdd={(id) => save(added(entries, id))} />
      <NotSetUp items={view.missing} />
    </section>
  );
}
