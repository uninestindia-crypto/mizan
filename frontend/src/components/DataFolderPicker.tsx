import { Download, FolderOpen, FolderSearch, RefreshCw } from "lucide-react";
import { useEffect } from "react";
import { errorMessage } from "../lib/api";
import { int } from "../lib/format";
import { useCancelDownload, usePickFolder, useScanForData, useStartDownload, useStatus } from "../lib/queries";
import { Button, Callout, cx, Field, Input, ProgressBar, Spinner } from "./ui";

/** Download the data for me: the answer for a computer that has none. */
export function DownloadData({ prominent }: { prominent: boolean }) {
  const status = useStatus();
  const start = useStartDownload();
  const cancel = useCancelDownload();
  const download = status.data?.download;
  if (!download) return null;
  const running = download.state === "RUNNING";

  if (running) {
    return (
      <div className="space-y-2 rounded-xl border border-brand/30 bg-brand/5 p-4">
        <ProgressBar value={download.progress} label="Downloading market data" />
        <div className="flex flex-wrap items-center justify-between gap-2 text-[12.5px] text-ink-3">
          <span>
            {download.message} {int(download.done)} of {int(download.total)} stocks
          </span>
          <Button size="sm" variant="ghost" loading={cancel.isPending} onClick={() => cancel.mutate()}>
            Stop
          </Button>
        </div>
      </div>
    );
  }

  const left = download.failures.length > 0 && (
    <details className="mt-1 text-[12px] text-ink-3">
      <summary className="cursor-pointer">
        {download.failed} stocks were left out by the data checks
        {download.without_actions > 0 ? ` · ${download.without_actions} without corporate-action history` : ""}
      </summary>
      <ul className="mt-1 space-y-0.5">
        {download.failures.map((f) => (
          <li key={f.symbol}>
            <span className="font-mono text-ink-2">{f.symbol}</span>: {f.reason}
          </li>
        ))}
      </ul>
    </details>
  );

  return (
    <div className={cx("rounded-xl border p-4", prominent ? "border-brand/40 bg-brand/5" : "border-line bg-surface-2/50")}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-[14rem] flex-1">
          <div className="text-[13.5px] font-semibold text-ink">
            {download.can_update ? "Update market data" : prominent ? "No market data yet? Download it." : "Download fresh data instead"}
          </div>
          <p className="mt-0.5 text-[12.5px] leading-relaxed text-ink-3">
            {download.can_update
              ? "Fetch the newest prices and corporate actions for the NIFTY 500 (the last three years are refreshed; your ten-year history stays). Takes about two to three minutes."
              : "NIFTY 500 stocks, ten years of daily prices and corporate actions, about 200 MB. Takes around seven minutes. It comes straight from the NSE and Upstox's public services to this computer, with no account needed."}
          </p>
        </div>
        <Button
          variant={prominent ? "primary" : "secondary"}
          icon={<Download className="size-4" aria-hidden />}
          loading={start.isPending}
          onClick={() => start.mutate(download.can_update ? "update" : "full")}
        >
          {download.can_update ? "Update market data" : "Download market data"}
        </Button>
      </div>
      {download.state === "ERROR" && (
        <Callout tone="danger" className="mt-3" title="The download did not finish">
          {download.message}
        </Callout>
      )}
      {download.state === "CANCELLED" && (
        <Callout tone="info" className="mt-3">
          {download.message}
        </Callout>
      )}
      {download.state === "DONE" && (
        <Callout tone="success" className="mt-3">
          {download.message}
        </Callout>
      )}
      {left}
      {start.isError && (
        <Callout tone="danger" className="mt-3">
          {errorMessage(start.error)}
        </Callout>
      )}
    </div>
  );
}

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
  const downloading = status.data?.download.state === "RUNNING";
  const best = candidates[0]?.path;

  // Select the best match as soon as one is found, unless a folder is already chosen. Not while a
  // download is filling a folder: that half-written folder is not data to connect yet.
  useEffect(() => {
    if (!path && best && !downloading) onPath(best);
  }, [path, best, downloading, onPath]);

  const browse = () =>
    pick.mutate(
      { title: "Choose your QuantOS data folder", initial: path || best || null },
      { onSuccess: (result) => result.path && onPath(result.path) },
    );

  const noneFound = !scanning && candidates.length === 0;
  return (
    <div className="space-y-4">
      {(noneFound || downloading) && <DownloadData prominent />}
      {!downloading && candidates.length > 0 && (
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

      {scanning && !downloading && (
        <div className="rounded-xl border border-line bg-surface-2/60 px-4 py-3">
          <Spinner label={candidates.length ? "Still searching your drives for more…" : "Looking for your market data on this computer…"} />
        </div>
      )}

      {noneFound && (
        <Callout tone="warn" title="We could not find market data on this computer">
          If you already have a QuantOS data folder, choose it with Browse. Otherwise use the download above, or skip this step and do it later in Settings.
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

      {!noneFound && !downloading && <DownloadData prominent={false} />}

      {(pick.isError || scan.isError) && (
        <Callout tone="danger">{errorMessage(pick.error ?? scan.error)}</Callout>
      )}
    </div>
  );
}
