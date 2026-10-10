import { date, int } from "../../lib/format";
import { useFilingCoverage } from "../../lib/proof";

/** "N stocks screened from company filings. Newest filing: ..." Nothing at all when the engine cannot say. */
export function FilingCoverageLine({ className }: { className?: string }) {
  const coverage = useFilingCoverage(true);
  const info = coverage.data;
  if (!info) return null;
  if (info.screened === 0) return <p className={className}>No stocks are screened from company filings yet.</p>;
  const newest = info.newest_filing ? ` Newest filing: ${date(info.newest_filing)}.` : "";
  return (
    <p className={className}>
      {int(info.screened)} {info.screened === 1 ? "stock is" : "stocks are"} screened from company filings.{newest}
    </p>
  );
}
