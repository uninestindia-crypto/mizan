import { type RefObject, useEffect, useRef } from "react";
import { ChatThread } from "./ChatThread";
import { Composer } from "./Composer";
import { useCopilot } from "./CopilotProvider";
import { DRAWER_NOTE_ID, DRAWER_TITLE_ID, DrawerHeader } from "./DrawerHeader";
import { HistoryPanel } from "./history/HistoryPanel";
import { useHistoryFocus } from "./history/useHistoryView";
import { WaysToAnswer } from "./WaysToAnswer";

// It starts below the top bar (h-14) so the Copilot button stays in reach and can close it again.
const PANEL_STYLE =
  "q-fade-in fixed bottom-0 right-0 top-14 z-30 flex w-full max-w-[440px] flex-col overflow-hidden border-l " +
  "border-line bg-surface shadow-[var(--shadow-pop)]";

/** Escape closes the drawer, unless a window on top of it (the Second opinion, the search) already took the key. */
function useEscapeToClose(open: boolean, close: () => void): void {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented || event.isComposing) return;
      event.preventDefault();
      close();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, close]);
}

function MessageArea({ input }: { input: RefObject<HTMLTextAreaElement | null> }) {
  return (
    <>
      <ChatThread />
      <div className="space-y-2 border-t border-line px-4 py-3">
        <WaysToAnswer />
        <Composer ref={input} />
        <p className="text-[12px] text-ink-3">
          The Copilot explains and looks things up. Its answers are information, not advice, and it never places an
          order.
        </p>
      </div>
    </>
  );
}

/**
 * The side panel, on every screen. It is not modal and does not trap the keyboard: the page behind it stays readable
 * and usable, Tab moves on in the page's own order, and clicking the page does not close it. Escape, Ctrl+J and the
 * close button do. Focus moves to the message box on open and returns to where the person was on close. The History
 * button swaps the thread for the saved chats; closing that panel puts focus back on the button.
 */
export function CopilotDrawer() {
  const { open, closeCopilot, restoreFocus, historyOpen, focusAfter } = useCopilot();
  const input = useRef<HTMLTextAreaElement>(null);
  const historyButton = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);
  useEscapeToClose(open, closeCopilot);
  useHistoryFocus({ historyOpen, focusAfter }, historyButton, input);
  useEffect(() => {
    if (open) input.current?.focus();
    else if (wasOpen.current) restoreFocus();
    wasOpen.current = open;
  }, [open, restoreFocus]);
  if (!open) return null;
  return (
    <div role="dialog" aria-labelledby={DRAWER_TITLE_ID} aria-describedby={DRAWER_NOTE_ID} className={PANEL_STYLE}>
      <DrawerHeader historyButton={historyButton} />
      {historyOpen ? <HistoryPanel /> : <MessageArea input={input} />}
    </div>
  );
}
