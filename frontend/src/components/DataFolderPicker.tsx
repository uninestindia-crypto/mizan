import { FolderOpen, FolderSearch, RefreshCw } from "lucide-react";
import { useEffect } from "react";
import { errorMessage } from "../lib/api";
import { int } from "../lib/format";
import { usePickFolder, useScanForData, useStatus } from "../lib/queries";
import { Button, Callout, cx, Field, Input, Spinner } from "./ui";

/**
 * Choosing the market-data folder without typing a path.
 *
 * QuantOS searches this computer by itself and lists what it finds, the best match already
 * selected. The person can pick another found folder, open the normal Windows folder dialog, or
 * (for the rare case) paste a path.
 */
export function DataFolderPicker({ path, onPath }: { path: string; onPath: (path: string) => void }) {
  const status = useStatus();
  const pick = usePickFolder();
  const scan = useScanForData();
  const folder = status.data?.data_folder;
  const candidates = folder?.candidates ?? [];
  const scanning = folder?.scan === "RUNNING" || scan.isPending;
  const best = candidates[0]?.path;

  // Select the best match as soon as one is found, unless a folder is already chosen.
  useEffect(() => {
    if (!path && best) onPath(best);
  }, [path, best, onPath]);

  const browse = () =>
    pick.mutate(
      { title: "Choose your QuantOS data folder", initial: path || best || null },
      { onSuccess: (result) => result.path && onPath(result.path) },
    );

  return (
    <div className="space-y-4">
      {candidates.length > 0 && (
        <div className="space-y-2">
          <div className="text-[12.5px] font-medium text-ink-3">Found on this computer</div>
          {candidates.map((candidate) => (
            <button
              key={candidate.path}
              type="button"
              onClick={() => onPath(candidate.path)}
              className={cx(
                "flex w-full items-center gap-3 rounded-xl border bg-surface px-4 py-3 text-left text-sm",
                path === candidate.path ? "border-brand ring-3 ring-brand/15" : "border-line hover:border-line-strong",
              )}
            >
              <FolderSearch className="size-4 shrink-0 text-brand" aria-hidden />
              <span className="min-w-0 flex-1 break-all font-mono text-[13px] text-ink">{candidate.path}</span>
              <span className="num shrink-0 text-[12.5px] text-ink-3">{int(candidate.datasets)} datasets</span>
            </button>
          ))}
        </div>
      )}

      {scanning && (
        <div className="rounded-xl border border-line bg-surface-2/60 px-4 py-3">
          <Spinner label={candidates.length ? "Still searching your drives for more…" : "Looking for your market data on this computer…"} />
        </div>
      )}

      {!scanning && candidates.length === 0 && (
        <Callout tone="warn" title="We could not find market data on this computer">
          Choose the folder that holds it with the Browse button below. If you do not have market data yet, you can skip this step and add it later in Settings.
        </Callout>
      )}

      <Field label="Selected folder" htmlFor="data-folder" hint="Pick any folder that contains your market data. QuantOS finds the right place inside it.">
        <div className="flex gap-2">
          <Input
            id="data-folder"
            value={path}
            onChange={(e) => onPath(e.target.value)}
            placeholder="No folder chosen yet"
            spellCheck={false}
            className="font-mono text-[13px]"
          />
          <Button variant="secondary" icon={<FolderOpen className="size-4" aria-hidden />} loading={pick.isPending} onClick={browse}>
            Browse…
          </Button>
        </div>
      </Field>

      <div className="flex flex-wrap items-center gap-3">
        <Button variant="ghost" size="sm" icon={<RefreshCw className="size-3.5" aria-hidden />} disabled={scanning} onClick={() => scan.mutate()}>
          Search again
        </Button>
        <span className="text-[12.5px] text-ink-3">Looks through your internal drives. Nothing leaves this computer.</span>
      </div>

      {(pick.isError || scan.isError) && (
        <Callout tone="danger">{errorMessage(pick.error ?? scan.error)}</Callout>
      )}
    </div>
  );
}
