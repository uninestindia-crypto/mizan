import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export interface Drawer {
  open: boolean;
  openCopilot: () => void;
  closeCopilot: () => void;
  toggleCopilot: () => void;
  /** The header buttons announce themselves so focus can go back to the right one when the drawer closes. */
  registerTrigger: (element: HTMLElement) => () => void;
  restoreFocus: () => void;
}

function isUsable(element: HTMLElement | null): element is HTMLElement {
  return !!element && element.isConnected && element !== document.body;
}

function isCopilotShortcut(event: KeyboardEvent): boolean {
  return (event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === "j";
}

/** Whether the drawer is open, where focus goes back to when it closes, and the Ctrl+J / Cmd+J shortcut. */
export function useDrawer(): Drawer {
  const [open, setOpen] = useState(false);
  const opener = useRef<HTMLElement | null>(null);
  const triggers = useRef(new Set<HTMLElement>());

  const openCopilot = useCallback(() => {
    const active = document.activeElement;
    opener.current = active instanceof HTMLElement ? active : null;
    setOpen(true);
  }, []);
  const closeCopilot = useCallback(() => setOpen(false), []);
  const toggleCopilot = useCallback(() => (open ? closeCopilot() : openCopilot()), [open, openCopilot, closeCopilot]);

  const registerTrigger = useCallback((element: HTMLElement) => {
    triggers.current.add(element);
    return () => void triggers.current.delete(element);
  }, []);

  const restoreFocus = useCallback(() => {
    if (isUsable(opener.current)) {
      opener.current.focus();
      return;
    }
    const buttons = [...triggers.current];
    (buttons.find((b) => b.getClientRects().length > 0) ?? buttons[0])?.focus();
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!isCopilotShortcut(event)) return;
      event.preventDefault();
      toggleCopilot();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggleCopilot]);

  return useMemo(
    () => ({ open, openCopilot, closeCopilot, toggleCopilot, registerTrigger, restoreFocus }),
    [open, openCopilot, closeCopilot, toggleCopilot, registerTrigger, restoreFocus],
  );
}
