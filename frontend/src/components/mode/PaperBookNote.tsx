import { cx } from "../ui";
import type { ModeLabels } from "./useModeLabels";

/**
 * One plain sentence above a paper book's table in Shariah mode. The table itself is never filtered: the book keeps
 * what its own rule holds and orders, and each row carries its Shariah label.
 */
export function PaperBookNote({ labels, className }: { labels: ModeLabels; className?: string }) {
  const style = cx("text-[12.5px] text-ink-2", className);
  if (!labels.active || labels.state === "loading" || labels.state === "off") return null;
  if (labels.note) {
    return (
      <p className={style} data-testid="paper-book-shariah-note">
        {labels.note} Every stock below shows as not screened. The book is unchanged.
      </p>
    );
  }
  const { notCompliant, notScreened } = labels;
  if (notCompliant + notScreened === 0) return null;
  const are = notCompliant === 1 ? "is" : "are";
  const first = notCompliant > 0 ? `${notCompliant} of these stocks ${are} not Shariah-compliant. ` : "";
  const have = notScreened === 1 ? "has" : "have";
  const second = notScreened > 0 ? `${notScreened} ${have} not been screened yet. ` : "";
  return (
    <p className={style} data-testid="paper-book-shariah-note">
      {first}
      {second}
      The book keeps them because it follows its own rule; QuantOS shows you the status so you can decide.
    </p>
  );
}
