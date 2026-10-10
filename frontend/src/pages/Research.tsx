import { ResearchScreen } from "../components/research/ResearchScreen";
import { PageHeader } from "../components/ui";

const SUBTITLE =
  "Ask a question in plain words and find the finance research papers closest to it. " +
  "These are papers to read. QuantOS does not turn them into advice or trading signals.";

export default function Research() {
  return (
    <>
      <PageHeader title="Research" subtitle={SUBTITLE} />
      <ResearchScreen />
    </>
  );
}
