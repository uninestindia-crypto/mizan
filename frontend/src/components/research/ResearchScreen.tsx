import { Search } from "lucide-react";
import { type FormEvent, useId, useState } from "react";
import { useResearchSearch, useResearchStatus } from "../../lib/research";
import { Button, Callout, EmptyState, Input, Spinner, Switch } from "../ui";
import { EngineCard } from "./EngineCard";
import { PaperCard } from "./PaperCard";

const EXAMPLES = [
  "How do I avoid overfitting a backtest?",
  "What is a deflated Sharpe ratio?",
  "How does market impact depend on order size?",
  "How should I size positions to manage risk?",
];

export function ResearchScreen() {
  const [question, setQuestion] = useState("");
  const [online, setOnline] = useState(false);
  const search = useResearchSearch();
  const status = useResearchStatus();
  const inputId = useId();
  const answer = search.data;

  const run = (text: string) => {
    if (text.trim()) search.mutate({ question: text.trim(), online });
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    run(question);
  };

  return (
    <div className="space-y-5">
      <form onSubmit={submit} className="space-y-3 rounded-2xl border border-line bg-surface p-5 shadow-2xs">
        <label htmlFor={inputId} className="block text-sm font-medium text-ink">
          Your question
        </label>
        <div className="flex flex-wrap gap-2">
          <div className="min-w-[16rem] flex-1">
            <Input
              id={inputId}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="For example: how do I avoid overfitting a backtest?"
              maxLength={500}
              autoComplete="off"
            />
          </div>
          <Button type="submit" icon={<Search className="size-4" aria-hidden />} loading={search.isPending} disabled={!question.trim()}>
            Search
          </Button>
        </div>
        <div className="flex flex-wrap items-center gap-2" aria-label="Example questions">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              className="rounded-full border border-line bg-surface-2 px-3 py-1 text-[12.5px] text-ink-2 hover:border-line-strong hover:text-ink"
              onClick={() => {
                setQuestion(example);
                run(example);
              }}
            >
              {example}
            </button>
          ))}
        </div>
        <Switch checked={online} onChange={setOnline} label="Also look for new papers on arXiv (needs internet)" />
      </form>

      <EngineCard />

      {search.isPending && <Spinner label="Searching the research library..." />}
      {search.isError && (
        <Callout tone="danger" title="The search did not work">
          {search.error.message}
        </Callout>
      )}

      {answer && !search.isPending && (
        <section aria-live="polite" className="space-y-3">
          {answer.notes.map((note) => (
            <Callout key={note} tone="info">
              {note}
            </Callout>
          ))}
          <h2 className="text-base font-semibold text-ink">
            {answer.results.length === 0
              ? "No papers matched"
              : `${answer.results.length} paper${answer.results.length === 1 ? "" : "s"} for "${answer.question}"`}
          </h2>
          <p className="text-[12.5px] text-ink-3">{answer.engine.label}</p>
          <p className="text-[12.5px] text-ink-3">
            {answer.engine.by_meaning
              ? "Compare the papers with each other. When matching by meaning, even an unrelated paper can score around 40%, so only a clearly higher number is a real fit."
              : "Compare the papers with each other. A paper that shares none of your words scores near 0%."}
          </p>
          {answer.results.length === 0 ? (
            <EmptyState title="Nothing close to that" body="Try other words, or turn on looking for new papers on arXiv." />
          ) : (
            answer.results.map((paper) => <PaperCard key={paper.id} paper={paper} />)
          )}
        </section>
      )}

      <p className="text-[12.5px] leading-relaxed text-ink-3">
        {status.data ? `Your library holds ${status.data.library.papers} papers on this computer. ` : ""}
        Match shows how closely a paper fits your question. It is not a prediction, and a paper is something to read, not
        advice or a signal to trade.
      </p>
    </div>
  );
}
