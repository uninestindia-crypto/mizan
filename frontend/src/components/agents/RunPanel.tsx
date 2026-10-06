import { type FormEvent, useEffect, useRef, useState } from "react";
import { type Agent, normalizeSymbol, SYMBOL_HINT, symbolProblem, useAgentRun } from "../../lib/agents";
import { Button, Callout, Field, Input, Spinner } from "../ui";
import { RunResultView } from "./RunResultView";

export const RUNNING_TEXT = "Running step by step... this can take a minute";

function SymbolForm({ running, onRun }: { running: boolean; onRun: (symbol: string) => void }) {
  const [text, setText] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found = symbolProblem(text);
    setProblem(found);
    if (!found) onRun(normalizeSymbol(text));
  };
  return (
    <form onSubmit={submit} className="flex flex-wrap items-start gap-3">
      <Field label="Which stock?" htmlFor="agent-run-symbol" hint={SYMBOL_HINT} error={problem}>
        <Input
          id="agent-run-symbol"
          value={text}
          placeholder="TCS"
          autoFocus
          autoComplete="off"
          className="w-52 uppercase"
          aria-invalid={problem ? true : undefined}
          onChange={(e) => setText(normalizeSymbol(e.target.value))}
        />
      </Field>
      <Button type="submit" loading={running} className="mt-[26px]">
        Run
      </Button>
    </form>
  );
}

/**
 * Starts an agent and shows what came back. The screen stays usable while it runs, and the answer is kept, so leaving
 * and coming back finds it. An agent that needs no stock starts as soon as this opens.
 */
export function RunPanel({ agent, onClose }: { agent: Agent; onClose: () => void }) {
  const { run, running, outcome } = useAgentRun(agent.id);
  const started = useRef(false);
  const autoStart = !agent.needs_symbol && !running && !outcome;

  useEffect(() => {
    if (autoStart && !started.current) {
      started.current = true;
      run(null);
    }
  }, [autoStart, run]);

  return (
    <div className="mt-4 border-t border-line pt-4" aria-live="polite">
      {agent.needs_symbol ? (
        <SymbolForm running={running} onRun={run} />
      ) : (
        <Button variant="secondary" loading={running} onClick={() => run(null)}>
          {outcome ? "Run again" : "Run"}
        </Button>
      )}
      {running && (
        <div className="mt-4">
          <Spinner label={RUNNING_TEXT} />
        </div>
      )}
      {!running && outcome && !outcome.ok && (
        <Callout tone="danger" className="mt-4">
          {outcome.message}
        </Callout>
      )}
      {!running && outcome?.ok && <RunResultView result={outcome.result} />}
      <div className="mt-4">
        <Button variant="ghost" size="sm" onClick={onClose}>
          Close
        </Button>
      </div>
    </div>
  );
}
