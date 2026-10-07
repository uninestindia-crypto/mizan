import { Sparkles } from "lucide-react";
import { useEffect, useRef } from "react";
import { useCopilot } from "./CopilotProvider";

// The wide button sits in the top bar, which sizes itself as a container. The word "Copilot" and the key hint appear
// only when the bar has room, so the button never pushes the bar past the edge of the window.
const WIDE_STYLE =
  "flex h-8 shrink-0 items-center gap-2 whitespace-nowrap rounded-[var(--radius-control)] border border-line " +
  "bg-surface-2 px-2.5 text-[12.5px] font-medium text-ink-2 transition-colors hover:border-line-strong " +
  "hover:text-ink @min-[760px]:px-3";
const WORD_STYLE = "hidden @min-[760px]:inline";
const KEY_HINT_STYLE =
  "hidden rounded border border-line bg-surface px-1.5 font-sans text-[10px] text-ink-3 @min-[900px]:inline";

export const COPILOT_TOOLTIP = "Copilot (Ctrl J)";

/** Opens the Copilot. The wide version sits in the top bar; the compact one in the phone-width bar. */
export function CopilotButton({ compact = false }: { compact?: boolean }) {
  const { open, toggleCopilot, registerTrigger } = useCopilot();
  const ref = useRef<HTMLButtonElement>(null);
  useEffect(() => (ref.current ? registerTrigger(ref.current) : undefined), [registerTrigger]);

  // The name stays "Copilot" when the word is hidden, and the tooltip tells a mouse user what Ctrl J does.
  const shared = {
    ref,
    type: "button",
    onClick: toggleCopilot,
    title: COPILOT_TOOLTIP,
    "aria-label": "Copilot",
    "aria-keyshortcuts": "Control+J",
    "aria-haspopup": "dialog",
    "aria-expanded": open,
  } as const;
  if (compact) {
    return (
      <button {...shared} className="rounded-lg p-2 text-ink-2 hover:bg-surface-2">
        <Sparkles className="size-5" aria-hidden />
      </button>
    );
  }
  return (
    <button {...shared} className={WIDE_STYLE}>
      <Sparkles className="size-3.5 text-brand" aria-hidden />
      <span className={WORD_STYLE}>Copilot</span>
      <kbd className={KEY_HINT_STYLE}>Ctrl J</kbd>
    </button>
  );
}
