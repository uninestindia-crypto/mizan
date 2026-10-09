import { FundamentalsScreen } from "../components/fundamentals/FundamentalsScreen";
import { PageHeader } from "../components/ui";

const SUBTITLE =
  "Find companies by facts from their own filings, using filters you choose, or put two to four side by side. " +
  "QuantOS shows facts and dates. It does not rank companies or tell you what to do.";

export default function Fundamentals() {
  return (
    <>
      <PageHeader title="Fundamentals" subtitle={SUBTITLE} />
      <FundamentalsScreen />
    </>
  );
}
