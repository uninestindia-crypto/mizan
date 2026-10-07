import { Pencil, Trash2 } from "lucide-react";
import { type RefObject, useEffect, useRef, useState } from "react";
import { type ChatSummary, messageCountLabel, whenLabel } from "../../../lib/copilotHistory";
import { Badge, cx } from "../../ui";
import { Confirm } from "./Confirm";
import { ICON_BUTTON, RenameForm } from "./RenameForm";
import type { ChatActions } from "./useChatActions";

type Mode = "view" | "rename" | "delete";
type Asking = Exclude<Mode, "view">;
type Tools = RefObject<Record<Asking, HTMLButtonElement | null>>;

/** What every row needs from the list around it. */
export interface RowContext {
  /** The chat in the thread now. */
  currentId: string | null;
  actions: ChatActions;
  onOpen: (id: string) => void;
  /** A chat was deleted, so its row is about to go and focus needs a new home. */
  onRemoved: () => void;
}

function ChatSummaryButton(props: { chat: ChatSummary; current: boolean; onOpen: (id: string) => void }) {
  const { chat, current, onOpen } = props;
  const facts = [whenLabel(chat.updatedAt), messageCountLabel(chat.messageCount)].filter(Boolean).join(" · ");
  return (
    <button
      type="button"
      onClick={() => onOpen(chat.id)}
      aria-current={current ? "true" : undefined}
      className="min-w-0 flex-1 rounded-xl px-3 py-2.5 text-left [overflow-wrap:anywhere]"
    >
      <span className="flex items-center gap-2">
        <span className="min-w-0 flex-1 truncate text-[13.5px] font-semibold text-ink">{chat.title}</span>
        {current && <Badge tone="brand">Open now</Badge>}
      </span>
      {chat.preview && <span className="mt-0.5 block truncate text-[12.5px] text-ink-2">{chat.preview}</span>}
      <span className="mt-1 block text-[12px] text-ink-3">{facts}</span>
    </button>
  );
}

interface RowToolsProps {
  title: string;
  tools: Tools;
  onAsk: (mode: Asking) => void;
}

/** Rename and Delete as icon buttons, always visible so a keyboard or a thumb finds them as easily as a mouse. */
function RowTools({ title, tools, onAsk }: RowToolsProps) {
  const keep = (name: Asking) => (element: HTMLButtonElement | null) => {
    if (tools.current) tools.current[name] = element;
  };
  return (
    <div className="flex shrink-0 gap-0.5 py-2 pr-2">
      <button
        ref={keep("rename")}
        type="button"
        onClick={() => onAsk("rename")}
        aria-label={`Rename chat: ${title}`}
        title="Rename"
        className={ICON_BUTTON}
      >
        <Pencil className="size-4" aria-hidden />
      </button>
      <button
        ref={keep("delete")}
        type="button"
        onClick={() => onAsk("delete")}
        aria-label={`Delete chat: ${title}`}
        title="Delete"
        className={ICON_BUTTON}
      >
        <Trash2 className="size-4" aria-hidden />
      </button>
    </div>
  );
}

/** When a rename or a delete question closes, focus goes back to the button that opened it. */
function useReturnFocus(mode: Mode, tools: Tools): void {
  const was = useRef<Mode>("view");
  useEffect(() => {
    if (mode === "view" && was.current !== "view") tools.current?.[was.current]?.focus();
    was.current = mode;
  }, [mode, tools]);
}

/** The open chat is tinted, a row that is asking something stands out, and the others wait for a hover. */
function rowTone(current: boolean, asking: boolean): string {
  if (current) return "border-brand/25 bg-brand-soft/50";
  return asking ? "border-line bg-surface-2" : "border-transparent hover:bg-surface-2";
}

interface ChatRowProps {
  chat: ChatSummary;
  context: RowContext;
}

/** One saved chat: click it to open it, or rename or delete it. Both ask in place, without leaving the list. */
export function ChatRow({ chat, context }: ChatRowProps) {
  const { currentId, actions, onOpen, onRemoved } = context;
  const [mode, setMode] = useState<Mode>("view");
  const tools = useRef<Record<Asking, HTMLButtonElement | null>>({ rename: null, delete: null });
  useReturnFocus(mode, tools);

  const current = chat.id === currentId;
  const toView = () => setMode("view");
  const removeThenMove = async () => {
    await actions.remove(chat.id);
    onRemoved();
  };
  const tone = rowTone(current, mode !== "view");
  return (
    <li className={cx("rounded-xl border transition-colors", tone)}>
      {mode === "rename" && <RenameForm chat={chat} rename={actions.rename} onDone={toView} />}
      {mode === "delete" && (
        <Confirm
          question="Delete this chat? This cannot be undone."
          confirmLabel="Delete"
          onConfirm={removeThenMove}
          onKeep={toView}
        />
      )}
      {mode === "view" && (
        <div className="flex items-start gap-0.5">
          <ChatSummaryButton chat={chat} current={current} onOpen={onOpen} />
          <RowTools title={chat.title} tools={tools} onAsk={setMode} />
        </div>
      )}
    </li>
  );
}
