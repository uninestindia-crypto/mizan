import { ExternalLink } from "lucide-react";
import { useState } from "react";
import type { ResearchPaper } from "../../lib/research";
import { Badge, Card, ProgressBar } from "../ui";

const SHORT = 280;

export function PaperCard({ paper }: { paper: ResearchPaper }) {
  const [open, setOpen] = useState(false);
  const long = paper.summary.length > SHORT;
  const text = open || !long ? paper.summary : `${paper.summary.slice(0, SHORT).trimEnd()}...`;
  const who = paper.authors.join(", ") + (paper.more_authors > 0 ? ` and ${paper.more_authors} more` : "");

  return (
    <Card>
      <article className="space-y-2 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h3 className="min-w-0 flex-1 text-[15px] font-semibold leading-snug text-ink">
            {paper.link ? (
              <a
                href={paper.link}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-start gap-1.5 hover:text-brand hover:underline"
              >
                <span>{paper.title}</span>
                <ExternalLink className="mt-1 size-3.5 shrink-0" aria-label="Opens the paper in your browser" />
              </a>
            ) : (
              paper.title
            )}
          </h3>
          <div className="w-32 shrink-0">
            <div className="mb-1 text-right text-[12px] font-medium text-ink-2">Match {paper.match_percent}%</div>
            <ProgressBar value={paper.match_percent / 100} label={`Match ${paper.match_percent} percent`} />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[12.5px] text-ink-3">
          <Badge>{paper.field}</Badge>
          <span>{paper.year}</span>
          {who && <span>{who}</span>}
        </div>
        <p className="text-[13.5px] leading-relaxed text-ink-2">{text}</p>
        {long && (
          <button
            type="button"
            className="text-[13px] font-medium text-brand hover:underline"
            onClick={() => setOpen((value) => !value)}
          >
            {open ? "Show less" : "Show more"}
          </button>
        )}
      </article>
    </Card>
  );
}
