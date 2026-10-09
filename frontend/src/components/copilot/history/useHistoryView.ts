import { type RefObject, useCallback, useEffect, useMemo, useRef, useState } from "react";

/** Where focus goes when the history panel closes: back to its button, or on to the message box. */
export type FocusAfter = "history" | "message";

export interface HistoryView {
  historyOpen: boolean;
  focusAfter: FocusAfter;
  openHistory: () => void;
  closeHistory: (focusAfter?: FocusAfter) => void;
  toggleHistory: () => void;
}

interface View {
  open: boolean;
  focusAfter: FocusAfter;
}

const CLOSED: View = { open: false, focusAfter: "history" };

/** Whether the history panel replaces the thread. Closing the drawer puts the thread back. */
export function useHistoryView(drawerOpen: boolean): HistoryView {
  const [view, setView] = useState<View>(CLOSED);
  useEffect(() => {
    if (!drawerOpen) setView((now) => (now.open ? CLOSED : now));
  }, [drawerOpen]);

  const openHistory = useCallback(() => setView({ open: true, focusAfter: "history" }), []);
  const closeHistory = useCallback(
    (focusAfter: FocusAfter = "history") => setView({ open: false, focusAfter }),
    [],
  );
  const toggleHistory = useCallback(
    () => setView((now) => (now.open ? { open: false, focusAfter: "history" } : { open: true, focusAfter: "history" })),
    [],
  );
  const { open, focusAfter } = view;
  return useMemo(
    () => ({ historyOpen: open, focusAfter, openHistory, closeHistory, toggleHistory }),
    [open, focusAfter, openHistory, closeHistory, toggleHistory],
  );
}

/** When the panel closes, focus goes to the History button, or to the message box after a chat was chosen. */
export function useHistoryFocus(
  view: Pick<HistoryView, "historyOpen" | "focusAfter">,
  button: RefObject<HTMLButtonElement | null>,
  message: RefObject<HTMLTextAreaElement | null>,
): void {
  const wasOpen = useRef(view.historyOpen);
  const { historyOpen, focusAfter } = view;
  useEffect(() => {
    if (wasOpen.current && !historyOpen) (focusAfter === "message" ? message : button).current?.focus();
    wasOpen.current = historyOpen;
  }, [historyOpen, focusAfter, button, message]);
}
