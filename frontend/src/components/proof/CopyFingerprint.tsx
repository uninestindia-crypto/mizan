import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Button } from "../ui";
import { shortHash } from "./proofFormat";

type Copied = "no" | "yes" | "failed";

/** The first 12 characters of the filing's fingerprint, and a button that copies the whole of it. */
export function CopyFingerprint({ hash }: { hash: string }) {
  const [copied, setCopied] = useState<Copied>("no");
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(hash);
      setCopied("yes");
    } catch {
      setCopied("failed");
    }
  };
  return (
    <span className="flex flex-wrap items-center gap-2">
      <code className="rounded bg-surface-2 px-1.5 py-0.5 text-[12.5px] text-ink" title={hash}>
        {shortHash(hash)}…
      </code>
      <Button
        variant="secondary"
        size="sm"
        icon={copied === "yes" ? <Check className="size-3.5" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
        onClick={() => void copy()}
        aria-label="Copy the full fingerprint"
        className="min-h-10 md:min-h-0"
      >
        {copied === "yes" ? "Copied" : "Copy"}
      </Button>
      <span role="status" className="text-[12.5px] text-ink-2">
        {copied === "failed" ? `Your browser would not allow copying. The full fingerprint is ${hash}` : ""}
      </span>
    </span>
  );
}
