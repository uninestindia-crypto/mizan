import { ChevronDown, ChevronUp, RefreshCw, Sparkles } from "lucide-react";
import { useState } from "react";
import { errorMessage } from "../../lib/api";
import { useCliCapabilities, useRefreshCliCapabilities } from "../../lib/queries";
import { readSizeWords, releasedWords, thinkingWords } from "../../lib/thinking";
import type { CliCapabilities, CliModel } from "../../lib/types";
import { Badge, Callout } from "../ui";

const CHIP = "rounded bg-surface-2 px-1.5 py-0.5 text-[10.5px] text-ink-2";

function ModelRow({ model }: { model: CliModel }) {
  const levels = model.thinking?.levels ?? [];
  const facts = [releasedWords(model.released), readSizeWords(model.context_window)].filter(Boolean);
  return (
    <li className="rounded border border-line/60 bg-surface p-2 text-[11.5px]">
      <div className="flex flex-wrap items-center justify-between gap-1.5">
        <span className="font-semibold text-ink">{model.name}</span>
        <span className="flex gap-1">
          {model.newest && <Badge tone="brand">Newest</Badge>}
          {model.recommended && <Badge tone="neutral">The app's first pick</Badge>}
        </span>
      </div>
      {model.description && <p className="mt-0.5 text-[11px] leading-snug text-ink-3">{model.description}</p>}
      {levels.length > 0 && (
        <div className="mt-1.5 flex flex-wrap items-center gap-1 text-[10.5px] text-ink-3">
          <span>Thinking:</span>
          {levels.map((level) => (
            <span key={level} className={CHIP}>
              {thinkingWords(level)}
              {model.thinking?.default === level ? " (its usual)" : ""}
            </span>
          ))}
        </div>
      )}
      {facts.length > 0 && <div className="mt-1 text-[10px] text-ink-3">{facts.join(" · ")}</div>}
    </li>
  );
}

function checkedAt(data: CliCapabilities): string {
  const when = new Date(data.saved_list_checked ?? data.last_fetched);
  if (Number.isNaN(when.getTime())) return "";
  return `Checked ${when.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}.`;
}

function Models({ data }: { data: CliCapabilities }) {
  return (
    <>
      {data.models.length > 0 && (
        <ul className="max-h-64 space-y-1.5 overflow-y-auto pr-1">
          {data.models.map((model) => (
            <ModelRow key={model.id} model={model} />
          ))}
        </ul>
      )}
      {data.note && <p className="text-[11px] leading-snug text-ink-3">{data.note}</p>}
      {data.features.length > 0 && (
        <ul className="space-y-0.5 border-t border-line/40 pt-2 text-[11px]">
          {data.features.map((fact) => (
            <li key={fact.name}>
              <span className="font-medium text-ink">{fact.name}: </span>
              <span className="text-ink-3">{fact.description}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="text-[10px] text-ink-3">
        {data.source_note} {checkedAt(data)}
      </p>
    </>
  );
}

/** The models one AI app can use right now, newest first, with the levels of thinking each accepts. */
export function ModelsPanel({ agentId, name, installed }: { agentId: string; name: string; installed: boolean }) {
  const [open, setOpen] = useState(false);
  const caps = useCliCapabilities(agentId, open && installed);
  const refresh = useRefreshCliCapabilities(agentId);
  if (!installed) return null;
  const busy = caps.isFetching || refresh.isPending;
  const error = refresh.isError ? refresh.error : caps.isError ? caps.error : null;

  return (
    <div className="mt-3 border-t border-line/60 pt-2.5">
      <button
        type="button"
        aria-label={`Models and thinking levels of ${name}`}
        aria-expanded={open}
        onClick={() => setOpen((before) => !before)}
        className="flex w-full items-center justify-between py-1 text-[12px] font-medium text-ink-2 transition-colors hover:text-ink"
      >
        <span className="flex items-center gap-1.5">
          <Sparkles className="size-3.5 text-brand" aria-hidden />
          <span>Models this app can use</span>
        </span>
        <span className="flex items-center gap-1 text-[11px] text-ink-3">
          {caps.data ? `${caps.data.models.length} found` : "See"}
          {open ? <ChevronUp className="size-3.5" aria-hidden /> : <ChevronDown className="size-3.5" aria-hidden />}
        </span>
      </button>

      {open && (
        <div className="mt-2 space-y-2.5 rounded-lg bg-surface-2/60 p-2.5 text-[12px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">Newest first</span>
            <button
              type="button"
              disabled={busy}
              onClick={() => refresh.mutate()}
              className="flex items-center gap-1 text-[11px] text-brand hover:underline disabled:opacity-50"
            >
              <RefreshCw className={`size-3 ${busy ? "animate-spin" : ""}`} aria-hidden />
              <span>{busy ? "Reading…" : "Refresh models"}</span>
            </button>
          </div>
          {caps.isLoading && <div className="py-2 text-center text-[11px] text-ink-3">Reading the models from {name}…</div>}
          {error && <Callout tone="danger">{errorMessage(error)}</Callout>}
          {caps.data && <Models data={caps.data} />}
        </div>
      )}
    </div>
  );
}
