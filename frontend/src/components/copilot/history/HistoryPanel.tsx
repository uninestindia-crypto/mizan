import { ArrowLeft, Lock, Search } from "lucide-react";
import { forwardRef, type KeyboardEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { useChatList } from "../../../lib/copilotHistory";
import { Callout } from "../../ui";
import { useCopilot } from "../CopilotProvider";
import { ClearAll } from "./ClearAll";
import { HistoryList } from "./HistoryList";
import { useChatActions } from "./useChatActions";
import { useDebouncedValue } from "./useDebouncedValue";

export const HISTORY_TITLE_ID = "copilot-history-title";
const SEARCH_ID = "copilot-history-search";
const SEARCH_DELAY_MS = 250;

const BACK_STYLE =
  "inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg px-2 text-[13px] font-medium text-ink-2 " +
  "hover:bg-surface-2 hover:text-ink";
const SEARCH_STYLE =
  "h-10 w-full rounded-[var(--radius-control)] border border-line bg-surface pl-9 pr-3 text-sm text-ink " +
  "placeholder:text-ink-3 hover:border-line-strong focus:border-brand focus:outline-none " +
  "focus:ring-3 focus:ring-brand/15";

const GONE = "That chat is no longer here. The list has been refreshed.";
const FAILED = "That chat could not be opened just now. Try again.";

/** What to tell the person when a chat they chose did not open, or null when it did (or the choice was overtaken). */
function problemWith(result: string): string | null {
  if (result === "missing") return GONE;
  return result === "failed" ? FAILED : null;
}

function PanelTop({ onBack, children }: { onBack: () => void; children: ReactNode }) {
  return (
    <div className="space-y-2.5 border-b border-line px-4 py-3">
      <div className="flex items-center justify-between gap-2">
        <h3 id={HISTORY_TITLE_ID} className="text-[15px] font-semibold text-ink">
          Your chats
        </h3>
        <button type="button" onClick={onBack} className={BACK_STYLE}>
          <ArrowLeft className="size-4" aria-hidden />
          Back to chat
        </button>
      </div>
      <p className="flex items-center gap-1.5 text-[12.5px] text-ink-3">
        <Lock className="size-3.5 shrink-0" aria-hidden />
        Your chats are saved on this computer only.
      </p>
      {children}
    </div>
  );
}

interface SearchFieldProps {
  value: string;
  onChange: (text: string) => void;
}

const SearchField = forwardRef<HTMLInputElement, SearchFieldProps>(function SearchField({ value, onChange }, ref) {
  return (
    <div className="relative">
      <label htmlFor={SEARCH_ID} className="sr-only">
        Search your chats
      </label>
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
      <input
        id={SEARCH_ID}
        ref={ref}
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Search your chats"
        autoComplete="off"
        className={SEARCH_STYLE}
      />
    </div>
  );
});

/**
 * The saved chats, in place of the thread. Click one to carry on with it. Everything is kept on this computer, and the
 * panel says so. Escape steps back to the chat; a rename or a delete question inside it takes Escape first.
 */
export function HistoryPanel() {
  const { closeHistory, openChat, chatId } = useCopilot();
  const actions = useChatActions();
  const search = useRef<HTMLInputElement>(null);
  const [typed, setTyped] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const query = useDebouncedValue(typed, SEARCH_DELAY_MS).trim();
  const list = useChatList(query);
  useEffect(() => search.current?.focus(), []);

  const open = async (id: string) => {
    setProblem(null);
    const result = await openChat(id);
    if (result === "opened") closeHistory("message");
    else setProblem(problemWith(result));
    if (result === "missing") void list.refetch();
  };
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key !== "Escape" || event.defaultPrevented) return;
    event.preventDefault();
    closeHistory();
  };
  const context = {
    currentId: chatId,
    actions,
    onOpen: (id: string) => void open(id),
    onRemoved: () => search.current?.focus(),
  };
  const showClear = query === "" && (list.data?.length ?? 0) > 0;
  return (
    <section aria-labelledby={HISTORY_TITLE_ID} onKeyDown={onKeyDown} className="flex min-h-0 flex-1 flex-col">
      <PanelTop onBack={() => closeHistory()}>
        <SearchField ref={search} value={typed} onChange={setTyped} />
      </PanelTop>
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-2.5 py-2.5">
        {problem && <Callout tone="warn">{problem}</Callout>}
        <HistoryList list={list} searching={query !== ""} context={context} />
      </div>
      {showClear && (
        <div className="border-t border-line">
          <ClearAll clearAll={actions.clearAll} />
        </div>
      )}
    </section>
  );
}
