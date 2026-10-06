import { Sparkles } from "lucide-react";
import { useEffect, useRef } from "react";
import { useCopilot } from "./CopilotProvider";

const WIDE_STYLE =
  "flex h-8 items-center gap-2 rounded-[var(--radius-control)] border border-line bg-surface-2 px-3 " +
  "text-[12.5px] font-medium text-ink-2 transition-colors hover:border-line-strong hover:text-ink";
const KEY_HINT_STYLE = "rounded border border-line bg-surface px-1.5 font-sans text-[10px] text-ink-3";

/** Opens the Copilot. The wide version sits in the top bar; the compact one in the phone-width bar. */
export function CopilotButton({ compact = false }: { compact?: boolean }) {
  const { open, toggleCopilot, registerTrigger } = useCopilot();
  const ref = useRef<HTMLButtonElement>(null);
  useEffect(() => (ref.current ? registerTrigger(ref.current) : undefined), [registerTrigger]);

  const shared = {
    ref,
    type: "button",
    onClick: toggleCopilot,
    "aria-haspopup": "dialog",
    "aria-expanded": open,
  } as const;
  if (compact) {
    return (
      <button {...shared} aria-label="Copilot" className="rounded-lg p-2 text-ink-2 hover:bg-surface-2">
        <Sparkles className="size-5" aria-hidden />
      </button>
    );
  }
  return (
    <button {...shared} className={WIDE_STYLE}>
      <Sparkles className="size-3.5 text-brand" aria-hidden />
      <span>Copilot</span>
      <kbd className={KEY_HINT_STYLE}>Ctrl J</kbd>
    </button>
  );
}
