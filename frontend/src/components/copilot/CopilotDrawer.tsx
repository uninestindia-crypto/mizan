import * as Dialog from "@radix-ui/react-dialog";
import { useRef } from "react";
import { ChatThread } from "./ChatThread";
import { Composer } from "./Composer";
import { useCopilot } from "./CopilotProvider";
import { DrawerHeader } from "./DrawerHeader";

const PANEL_STYLE =
  "q-fade-in fixed inset-y-0 right-0 z-30 flex w-full max-w-[440px] flex-col border-l border-line bg-surface " +
  "shadow-[var(--shadow-pop)]";

/**
 * The side panel, on every screen. It is not modal: the page behind it stays readable and usable, and clicking
 * the page does not close it. Escape and the close button do. Focus moves to the message box on open and
 * returns to where the person was on close.
 */
export function CopilotDrawer() {
  const { open, openCopilot, closeCopilot, restoreFocus } = useCopilot();
  const input = useRef<HTMLTextAreaElement>(null);
  return (
    <Dialog.Root open={open} onOpenChange={(next) => (next ? openCopilot() : closeCopilot())} modal={false}>
      <Dialog.Portal>
        <Dialog.Content
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            input.current?.focus();
          }}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            restoreFocus();
          }}
          onInteractOutside={(event) => event.preventDefault()}
          className={PANEL_STYLE}
        >
          <DrawerHeader />
          <ChatThread />
          <div className="space-y-2 border-t border-line px-4 py-3">
            <Composer ref={input} />
            <p className="text-[12px] text-ink-3">
              The Copilot explains and looks things up. Its answers are information, not advice, and it never places
              an order.
            </p>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
