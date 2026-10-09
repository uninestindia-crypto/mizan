import type { ReactNode } from "react";

const SUMMARY =
  "min-h-10 cursor-pointer select-none py-2 text-[13px] font-medium text-brand hover:underline md:min-h-0 md:py-0";

/** A line that opens to show more. It is the browser's own control, so keys and screen readers already work. */
export function Disclosure({ title, children }: { title: string; children: ReactNode }) {
  return (
    <details className="text-[13px]">
      <summary className={SUMMARY}>{title}</summary>
      <div className="mt-2">{children}</div>
    </details>
  );
}
