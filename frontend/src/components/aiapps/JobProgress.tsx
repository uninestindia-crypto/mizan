import { ExternalLink } from "lucide-react";
import { useState } from "react";
import { errorMessage } from "../../lib/api";
import { useSendCliCode } from "../../lib/queries";
import type { AgentCliJob } from "../../lib/types";
import { Button, Input, Spinner } from "../ui";

function SignInLink({ url }: { url: string }) {
  return (
    <div className="mt-2 text-ink-3">
      Browser did not open?{" "}
      <a href={url} target="_blank" rel="noreferrer" className="font-medium text-brand hover:underline">
        Open the sign-in page <ExternalLink className="inline size-3" aria-hidden />
      </a>
    </div>
  );
}

/** A sign-in page can show a code. This is where a person pastes it back. */
function CodeBox({ agentId }: { agentId: string }) {
  const send = useSendCliCode();
  const [code, setCode] = useState("");
  const submit = () => {
    const text = code.trim();
    if (text) send.mutate({ agentId, text }, { onSuccess: () => setCode("") });
  };
  return (
    <>
      <form
        className="mt-2 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <Input
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="If the page shows a code, paste it here"
          spellCheck={false}
          aria-label="Sign-in code"
          className="font-mono text-[12px]"
        />
        <Button size="sm" type="submit" loading={send.isPending} disabled={!code.trim()}>
          Submit
        </Button>
      </form>
      {send.isError && <div className="mt-1 text-[11.5px] text-down">{errorMessage(send.error)}</div>}
    </>
  );
}

/** What an install or a sign-in is doing right now, with the sign-in page and code box when there is one. */
export function JobProgress({ agentId, job }: { agentId: string; job: AgentCliJob }) {
  return (
    <div className="mt-3 rounded-lg border border-brand/30 bg-brand/5 p-3 text-[12.5px]">
      <Spinner label={job.message || "Working…"} />
      {job.action === "signin" && job.url && <SignInLink url={job.url} />}
      {job.accepts_code && job.url && <CodeBox agentId={agentId} />}
      <div className="mt-1 text-[11.5px] text-ink-3">{Math.round(job.seconds)}s</div>
    </div>
  );
}
