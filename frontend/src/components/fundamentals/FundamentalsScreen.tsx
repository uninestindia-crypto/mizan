import { useState } from "react";
import { useSearchParams } from "react-router";
import { errorMessage } from "../../lib/api";
import { useFundamentalsScreen } from "../../lib/fundamentalsQueries";
import type { ScreenParams } from "../../lib/fundamentalsTypes";
import { Callout, Card, Segmented, Skeleton } from "../ui";
import { CompareView } from "./CompareView";
import { ScreenForm } from "./ScreenForm";
import { ScreenResults } from "./ScreenResults";
import { EMPTY_PARAMS } from "./screenWords";

const VIEWS: { value: string; label: string }[] = [
  { value: "filter", label: "Filter companies" },
  { value: "compare", label: "Compare side by side" },
];

function Filter() {
  const [draft, setDraft] = useState<ScreenParams>(EMPTY_PARAMS);
  const [chosen, setChosen] = useState<ScreenParams | null>(null);
  const found = useFundamentalsScreen(chosen);
  const run = () => setChosen({ ...draft });
  return (
    <div className="space-y-4">
      <Card>
        <ScreenForm draft={draft} onChange={setDraft} onRun={run} running={found.isFetching} />
      </Card>
      {chosen !== null && found.isPending && <Skeleton className="h-48" />}
      {found.isError && (
        <Callout tone="danger" title="The companies could not be listed">
          {errorMessage(found.error)}
        </Callout>
      )}
      {found.data && <ScreenResults answer={found.data} busy={found.isPlaceholderData} />}
    </div>
  );
}

/** One value kept in the address (?name=value), so the screen can be linked to and survives a reload. */
function useParam(name: string): [string, (value: string) => void] {
  const [params, setParams] = useSearchParams();
  const set = (value: string) => {
    const after = new URLSearchParams(params);
    if (value) after.set(name, value);
    else after.delete(name);
    setParams(after, { replace: true });
  };
  return [params.get(name) ?? "", set];
}

/** Find companies with filters you choose, or put two to four side by side. Facts only, nothing ranked or advised. */
export function FundamentalsScreen() {
  const [view, setView] = useParam("view");
  const [listed, setListed] = useParam("symbols");
  const symbols = listed.split(",").filter(Boolean);
  const compare = view === "compare";
  return (
    <div className="space-y-5">
      <Segmented
        label="What to do"
        value={compare ? "compare" : "filter"}
        onChange={setView}
        options={VIEWS}
      />
      {compare ? <CompareView symbols={symbols} onChange={(next) => setListed(next.join(","))} /> : <Filter />}
    </div>
  );
}
