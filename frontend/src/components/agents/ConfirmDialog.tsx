import type { ReactNode } from "react";
import { Button, Dialog } from "../ui";

interface Props {
  open: boolean;
  title: string;
  body: ReactNode;
  choices: { keep: string; confirm: string };
  onAnswer: (confirmed: boolean) => void;
  busy?: boolean;
  /** Where focus goes when the button that opened this question is gone by the time it closes. */
  fallbackFocus?: () => HTMLElement | null;
}

/** An in-app question with two plain answers. Never the browser's own pop-up. */
export function ConfirmDialog(props: Props) {
  const { open, title, body, choices, onAnswer, busy = false, fallbackFocus } = props;
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => !next && onAnswer(false)}
      title={title}
      fallbackFocus={fallbackFocus}
      footer={
        <>
          <Button variant="secondary" onClick={() => onAnswer(false)}>
            {choices.keep}
          </Button>
          <Button variant="danger" loading={busy} onClick={() => onAnswer(true)}>
            {choices.confirm}
          </Button>
        </>
      }
    >
      <div className="text-sm text-ink-2">{body}</div>
    </Dialog>
  );
}
