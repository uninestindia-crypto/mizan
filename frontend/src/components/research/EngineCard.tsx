import { CheckCircle2, Sparkles } from "lucide-react";
import { type ApiError } from "../../lib/api";
import {
  type ResearchStatus,
  useCancelResearchSetup,
  useResearchStatus,
  useStartResearchSetup,
} from "../../lib/research";
import { Badge, Button, Callout, Card, CardHeader, ProgressBar, Spinner } from "../ui";

function startError(error: ApiError | null): string | null {
  return error ? error.message : null;
}

/** How matching works right now, and the one button that turns on matching by meaning. */
export function EngineCard() {
  const status = useResearchStatus();
  const start = useStartResearchSetup();
  const cancel = useCancelResearchSetup();

  if (status.isPending) return null;
  if (status.isError || !status.data) return null;
  const { engine, setup } = status.data;
  const working = setup.state === "DOWNLOADING" || setup.state === "PREPARING";

  return (
    <Card>
      <CardHeader
        title="How matching works"
        subtitle="Search can match papers by their wording, or by their meaning."
        action={
          <Badge tone={engine.by_meaning ? "up" : "neutral"}>
            {engine.by_meaning ? "Matching by meaning" : "Matching by keywords"}
          </Badge>
        }
      />
      <div className="space-y-3 p-5 pt-0 text-[13.5px] text-ink-2">
        {engine.by_meaning ? (
          <p className="flex items-start gap-2">
            <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-up" aria-hidden />
            <span>
              Google's EmbeddingGemma 2 is running on this computer. What you type stays here and the search works without
              internet.
            </span>
          </p>
        ) : (
          <p>{describeKeywordMatching(status.data)}</p>
        )}

        {working && (
          <div className="space-y-2">
            {setup.state === "DOWNLOADING" ? (
              <>
                <ProgressBar value={setup.percent / 100} label="Download progress" />
                <p aria-live="polite">{setup.message}</p>
              </>
            ) : (
              <Spinner label={setup.message || "Getting the research library ready..."} />
            )}
            {setup.state === "DOWNLOADING" && (
              <Button variant="secondary" size="sm" onClick={() => cancel.mutate()} loading={cancel.isPending}>
                Cancel the download
              </Button>
            )}
          </div>
        )}

        {setup.state === "FAILED" && (
          <Callout
            tone="danger"
            title="Smarter search was not turned on"
            action={
              <Button size="sm" onClick={() => start.mutate()} loading={start.isPending}>
                Try again
              </Button>
            }
          >
            {setup.error?.message ?? setup.message}
          </Callout>
        )}
        {setup.state === "CANCELLED" && (
          <Callout
            tone="info"
            title="Download cancelled"
            action={
              <Button size="sm" onClick={() => start.mutate()} loading={start.isPending}>
                Start again
              </Button>
            }
          >
            What was already downloaded is kept, so starting again carries on from there.
          </Callout>
        )}
        {setup.state === "DONE" && engine.by_meaning && (
          <Callout tone="success" title="Smarter search is on">
            {setup.message}
          </Callout>
        )}

        {!working && !engine.by_meaning && engine.state === "NEEDS_DOWNLOAD" && setup.state !== "FAILED" && setup.state !== "CANCELLED" && (
          <div>
            <Button icon={<Sparkles className="size-4" aria-hidden />} onClick={() => start.mutate()} loading={start.isPending}>
              Turn on smarter search
            </Button>
          </div>
        )}
        {startError(start.error) && (
          <Callout tone="danger" title="Could not start">
            {startError(start.error)}
          </Callout>
        )}
      </div>
    </Card>
  );
}

function describeKeywordMatching(status: ResearchStatus): string {
  if (status.engine.state === "NOT_INSTALLED") {
    return "Smarter search is not available in this copy of QuantOS. Search keeps working by matching the words in your question.";
  }
  return (
    "Right now search matches the words in your question with the words in each paper. To match by meaning, turn on " +
    `smarter search. It downloads Google's EmbeddingGemma 2 once (about ${status.engine.download_mb} MB), then works without ` +
    "internet. Nothing you type is sent anywhere."
  );
}
