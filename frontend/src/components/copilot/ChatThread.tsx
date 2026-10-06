import { Loader2 } from "lucide-react";
import { useEffect, useRef } from "react";
import { Button, Callout } from "../ui";
import { ChatMessageView } from "./ChatMessageView";
import { useCopilot } from "./CopilotProvider";

export const STARTERS = ["Is TCS halal?", "How is INFY doing?", "News on RELIANCE", "What can you do?"];

const STARTER_STYLE =
  "rounded-full border border-line bg-surface px-3 py-1.5 text-[13px] text-ink-2 transition-colors " +
  "hover:border-line-strong hover:bg-surface-2 hover:text-ink";

function Starters({ onPick }: { onPick: (text: string) => void }) {
  return (
    <div className="space-y-4 py-2">
      <div>
        <h3 className="text-[15px] font-semibold text-ink">Ask the Copilot</h3>
        <p className="mt-1 text-[13.5px] text-ink-2">
          It can look up a stock, check halal screening, read recent headlines and explain what you see on screen. It
          never places an order.
        </p>
      </div>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Things to ask">
        {STARTERS.map((text) => (
          <button key={text} type="button" onClick={() => onPick(text)} className={STARTER_STYLE}>
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}

function Thinking() {
  return (
    <p role="status" className="flex items-center gap-2 text-[13px] text-ink-3">
      <Loader2 className="size-4 animate-spin" aria-hidden />
      Thinking…
    </p>
  );
}

function CouldNotAnswer({ onRetry }: { onRetry: () => void }) {
  const retry = (
    <Button size="sm" variant="secondary" onClick={onRetry}>
      Retry
    </Button>
  );
  return (
    <Callout tone="warn" action={retry}>
      The Copilot could not answer just now. Check that QuantOS is running and try again.
    </Callout>
  );
}

export function ChatThread() {
  const { messages, thinking, failed, send, retry } = useCopilot();
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const box = scroller.current;
    if (box) box.scrollTop = box.scrollHeight;
  }, [messages.length, thinking, failed]);

  const empty = messages.length === 0 && !thinking && !failed;
  return (
    <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
      {empty && <Starters onPick={send} />}
      <div role="log" aria-label="Conversation" aria-live="polite" aria-relevant="additions" className="space-y-4">
        {messages.map((message) => (
          <ChatMessageView key={message.id} message={message} />
        ))}
        {thinking && <Thinking />}
        {failed && <CouldNotAnswer onRetry={retry} />}
      </div>
    </div>
  );
}
