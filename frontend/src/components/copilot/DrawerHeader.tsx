import { History, MessageSquarePlus, X } from "lucide-react";
import type { RefObject } from "react";
import { useCopilot } from "./CopilotProvider";

export const DRAWER_TITLE_ID = "copilot-drawer-title";
export const DRAWER_NOTE_ID = "copilot-drawer-note";

const CLOSE_STYLE = "rounded-lg p-1.5 text-ink-3 hover:bg-surface-2 hover:text-ink";
const BUTTON_STYLE =
  "inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-[13px] font-medium text-ink-2 " +
  "hover:bg-surface-2 hover:text-ink disabled:cursor-not-allowed disabled:opacity-50";
const HISTORY_ON = "bg-surface-2 text-ink";
// The header is its own container, so the word "History" appears only when the drawer is wide enough for it.
const HISTORY_WORD = "hidden @min-[380px]:inline";

type ButtonRef = RefObject<HTMLButtonElement | null>;

/** History, New chat and Close. History keeps its name for a screen reader even when only its icon fits. */
function HeaderButtons({ historyButton }: { historyButton: ButtonRef }) {
  const { newChat, closeCopilot, messages, thinking, historyOpen, toggleHistory, closeHistory } = useCopilot();
  const hasChat = messages.length > 0 || thinking;
  const startNew = () => {
    newChat();
    if (historyOpen) closeHistory("message");
  };
  return (
    <div className="flex shrink-0 items-center gap-1">
      <button
        ref={historyButton}
        type="button"
        onClick={toggleHistory}
        aria-pressed={historyOpen}
        aria-label="History"
        title="Your saved chats"
        className={`${BUTTON_STYLE} ${historyOpen ? HISTORY_ON : ""}`}
      >
        <History className="size-4" aria-hidden />
        <span className={HISTORY_WORD}>History</span>
      </button>
      <button type="button" onClick={startNew} disabled={!hasChat && !historyOpen} className={BUTTON_STYLE}>
        <MessageSquarePlus className="size-4" aria-hidden />
        New chat
      </button>
      <button type="button" onClick={closeCopilot} className={CLOSE_STYLE} aria-label="Close Copilot">
        <X className="size-5" aria-hidden />
      </button>
    </div>
  );
}

/** The Copilot's title and its buttons on one line, with the one-line note under them across the full width. */
export function DrawerHeader({ historyButton }: { historyButton: ButtonRef }) {
  return (
    <div className="@container border-b border-line px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <h2 id={DRAWER_TITLE_ID} className="min-w-0 text-[15px] font-semibold text-ink">
          Copilot
        </h2>
        <HeaderButtons historyButton={historyButton} />
      </div>
      <p id={DRAWER_NOTE_ID} className="mt-0.5 text-[12.5px] text-ink-3">
        Ask about a stock, a screen or a result.
      </p>
    </div>
  );
}
