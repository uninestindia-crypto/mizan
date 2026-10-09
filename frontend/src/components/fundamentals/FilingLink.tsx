import { ExternalLink } from "lucide-react";
import { safeNseUrl } from "../../lib/proof";

/** A link to the filing only when the address really is on NSE's own sites. Anything else is shown as plain text. */
export function FilingLink({ url, children }: { url: string | null; children: string }) {
  if (!url) return null;
  const safe = safeNseUrl(url);
  if (!safe) {
    return (
      <span className="break-all text-ink-2">
        {children}: <span className="text-ink-3">{url}</span> (not a link, because it is not on NSE's site)
      </span>
    );
  }
  return (
    <a
      href={safe}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex min-h-10 items-center gap-1 font-medium text-brand hover:underline md:min-h-0"
    >
      {children}
      <ExternalLink className="size-3.5" aria-hidden />
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  );
}
