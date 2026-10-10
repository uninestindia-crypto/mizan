import { SendHorizontal } from "lucide-react";
import { forwardRef, type KeyboardEvent } from "react";
import { lengthNote, MAX_MESSAGE_CHARS } from "../../lib/copilot";
import { Button } from "../ui";
import { useCopilot } from "./CopilotProvider";

const BOX_STYLE =
  "min-h-10 w-full resize-none rounded-[var(--radius-control)] border border-line bg-surface px-3 py-2 text-sm " +
  "text-ink placeholder:text-ink-3 hover:border-line-strong focus:border-brand focus:outline-none " +
  "focus:ring-3 focus:ring-brand/15";

const NOTE_ID = "copilot-length";

/** How long the message is, once it is nearly too long. At the limit it says so in a plain sentence. */
function LengthNote({ count }: { count: number }) {
  const note = lengthNote(count);
  if (!note) return null;
  const atLimit = count >= MAX_MESSAGE_CHARS;
  const style = atLimit ? "text-[12px] text-warn" : "text-right text-[12px] text-ink-3";
  return (
    <p id={NOTE_ID} role={atLimit ? "status" : undefined} className={style}>
      {note}
    </p>
  );
}

/** The message box. Enter sends; Shift+Enter adds a new line. */
export const Composer = forwardRef<HTMLTextAreaElement>(function Composer(_props, ref) {
  const { draft, setDraft, send, thinking } = useCopilot();
  const canSend = !thinking && draft.trim() !== "";
  const submit = () => {
    if (canSend && send(draft)) setDraft("");
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    submit();
  };
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
      className="space-y-1.5"
    >
      <div className="flex items-end gap-2">
        <label htmlFor="copilot-message" className="sr-only">
          Your message to the Copilot
        </label>
        <textarea
          id="copilot-message"
          ref={ref}
          rows={Math.min(5, Math.max(1, draft.split("\n").length))}
          value={draft}
          maxLength={MAX_MESSAGE_CHARS}
          aria-describedby={lengthNote(draft.length) ? NOTE_ID : undefined}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask about a stock"
          className={BOX_STYLE}
        />
        <Button type="submit" disabled={!canSend} icon={<SendHorizontal className="size-4" aria-hidden />}>
          Send
        </Button>
      </div>
      <LengthNote count={draft.length} />
    </form>
  );
});
