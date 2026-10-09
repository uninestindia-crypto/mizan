import { useState } from "react";
import { AcademyTab } from "../components/shariah/AcademyTab";
import { BasketsTab } from "../components/shariah/BasketsTab";
import { PurificationTab } from "../components/shariah/PurificationTab";
import { ScreenerTab } from "../components/shariah/ScreenerTab";
import { ShariahTabs, type ShariahTab } from "../components/shariah/ShariahTabs";
import { ZakatTab } from "../components/shariah/ZakatTab";
import { Badge, Callout, PageHeader } from "../components/ui";
import { int } from "../lib/format";
import { useShariahBaskets, useShariahComplianceSummary, useShariahStatus } from "../lib/shariah";

const SUBTITLE =
  "Dual-standard (AAOIFI & TASIS) equity screening, thematic halal baskets, dividend purification, and zakat " +
  "calculation.";
const PILL = "flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5 text-[13px] shadow-sm";

function SampleCount({ count }: { count: number }) {
  return (
    <div className={PILL}>
      <span className="size-2 animate-pulse rounded-full bg-up" />
      <span className="num font-medium text-ink-2">{int(count)} sample equities</span>
      <Badge tone="warn">Illustrative data</Badge>
    </div>
  );
}

function Panels({ tab }: { tab: ShariahTab }) {
  const summary = useShariahComplianceSummary();
  const baskets = useShariahBaskets();
  if (tab === "screener") return <ScreenerTab summary={summary.data ?? []} />;
  if (tab === "baskets") return <BasketsTab baskets={baskets.data ?? []} />;
  if (tab === "purification") return <PurificationTab />;
  if (tab === "zakat") return <ZakatTab />;
  return <AcademyTab />;
}

export default function Shariah() {
  const [tab, setTab] = useState<ShariahTab>("screener");
  const status = useShariahStatus();

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Ethical Wealth & Compliance"
        title="Mizan Shariah"
        subtitle={SUBTITLE}
        actions={status.data ? <SampleCount count={status.data.companies_seeded} /> : undefined}
      />
      <Callout tone="warn" title="Sample data, not live and not audited">
        The companies, financial ratios and basket lists on this page are an illustrative sample entered by hand from
        FY24 reports. They are not read from audited filings and no price here is live (the prices in Markets are the
        real ones). Do not buy, sell or avoid a share on the strength of a verdict shown here.
      </Callout>
      <ShariahTabs tab={tab} onTab={setTab} />
      <Panels tab={tab} />
    </div>
  );
}
