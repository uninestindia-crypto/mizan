import { ExternalLink, RefreshCw } from "lucide-react";
import { date } from "../../lib/format";
import { useUpdate } from "../../lib/queries";
import type { UpdateInfo } from "../../lib/types";
import { Button, Callout, Dialog } from "../ui";
import { UpdateProgress } from "./UpdateProgress";
import { plainNotes, WINDOWS_NOTE } from "./updateInstall";
import { type InstallUpdate, useInstallUpdate } from "./useInstallUpdate";

const RELEASE_LINK =
  "inline-flex shrink-0 items-center gap-1 whitespace-nowrap text-[12.5px] font-medium text-brand hover:underline";
// On a window too short for everything, the body scrolls instead of the window's top and bottom being cut off.
// The padding keeps the focus rings of the controls at its edges from being clipped.
const SCROLL =
  "-mx-1.5 max-h-[calc(100dvh-14rem)] overflow-y-auto px-1.5 sm:max-h-[calc(100dvh-11rem)]";
const NOTES =
  "max-h-[clamp(5rem,26vh,13rem)] overflow-y-auto whitespace-pre-wrap rounded-lg border border-line bg-surface-2 " +
  "p-3 text-[13px] leading-relaxed text-ink-2";

function WhatsNew({ info }: { info: UpdateInfo }) {
  const notes = plainNotes(info.notes);
  return (
    <section aria-label="What is new" className="mb-4">
      <div className="mb-1.5 flex items-center justify-between gap-3">
        <h3 className="text-[13px] font-semibold text-ink">What is new</h3>
        {info.url && (
          <a href={info.url} target="_blank" rel="noreferrer" className={RELEASE_LINK}>
            Open the release page
            <ExternalLink className="size-3.5" aria-hidden />
          </a>
        )}
      </div>
      {notes ? (
        <div tabIndex={0} className={NOTES}>
          {notes}
        </div>
      ) : (
        <p className="text-[13px] text-ink-2">The release page lists everything that changed.</p>
      )}
    </section>
  );
}

function Actions({ install, close }: { install: InstallUpdate; close: () => void }) {
  const { status, working, starting } = install;
  const label = working ? "Updating…" : status.state === "failed" ? "Try again" : "Update and restart";
  return (
    <div className="mt-5 flex flex-wrap items-center justify-end gap-2">
      <Button variant="secondary" onClick={close}>
        {working ? "Close" : "Not now"}
      </Button>
      <Button
        onClick={install.start}
        disabled={working}
        loading={starting}
        icon={starting ? undefined : <RefreshCw className="size-4" aria-hidden />}
      >
        {label}
      </Button>
    </div>
  );
}

function Body({ info, close }: { info: UpdateInfo; close: () => void }) {
  const install = useInstallUpdate();
  const { status, refusal, working } = install;
  return (
    <div className={SCROLL}>
      <WhatsNew info={info} />
      <UpdateProgress status={status} />
      {refusal && <Callout tone="warn">{refusal}</Callout>}
      {!working && <p className="mt-3 text-[12.5px] text-ink-3">{WINDOWS_NOTE}</p>}
      <Actions install={install} close={close} />
    </div>
  );
}

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Where focus goes when the control that opened the window has gone (for example, a chip that hides itself). */
  fallbackFocus?: () => HTMLElement | null;
}

/**
 * What is new in the latest QuantOS, and the "Update and restart" button with its progress. It reads the update notice
 * itself, so any screen can mount it: `<UpdateDialog open={open} onOpenChange={setOpen} />`.
 */
export function UpdateDialog({ open, onOpenChange, fallbackFocus }: Props) {
  const info = useUpdate().data;
  const ready = Boolean(info?.update_available && info.latest);
  const title = ready ? `QuantOS ${info?.latest} is ready` : "QuantOS is up to date";
  const released = info?.published_at ? ` Released ${date(info.published_at)}.` : "";
  const description = ready
    ? `You have version ${info?.current}.${released} Your portfolio, paper books and settings are kept.`
    : "There is nothing newer than the version you have right now.";
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description={description}
      fallbackFocus={fallbackFocus}
    >
      {ready && info ? <Body info={info} close={() => onOpenChange(false)} /> : null}
    </Dialog>
  );
}
