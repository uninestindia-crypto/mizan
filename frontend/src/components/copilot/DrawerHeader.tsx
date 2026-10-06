import { MessageSquarePlus, X } from "lucide-react";
import { useCopilot } from "./CopilotProvider";

export const DRAWER_TITLE_ID = "copilot-drawer-title";
export const DRAWER_NOTE_ID = "copilot-drawer-note";

const CLOSE_STYLE = "rounded-lg p-1.5 text-ink-3 hover:bg-surface-2 hover:text-ink";
const NEW_CHAT_STYLE =
  "inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-[13px] font-medium text-ink-2 " +
  "hover:bg-surface-2 hover:text-ink disabled:cursor-not-allowed disabled:opacity-50";

export function DrawerHeader() {
  const { newChat, closeCopilot, messages, thinking } = useCopilot();
  const hasChat = messages.length > 0 || thinking;
  return (
    <div className="flex items-start justify-between gap-3 border-b border-line px-4 py-3">
      <div className="min-w-0">
        <h2 id={DRAWER_TITLE_ID} className="text-[15px] font-semibold text-ink">
          Copilot
        </h2>
        <p id={DRAWER_NOTE_ID} className="text-[12.5px] text-ink-3">
          Ask about a stock, a screen or a result.
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <button type="button" onClick={newChat} disabled={!hasChat} className={NEW_CHAT_STYLE}>
          <MessageSquarePlus className="size-4" aria-hidden />
          New chat
        </button>
        <button type="button" onClick={closeCopilot} className={CLOSE_STYLE} aria-label="Close Copilot">
          <X className="size-5" aria-hidden />
        </button>
      </div>
    </div>
  );
}
