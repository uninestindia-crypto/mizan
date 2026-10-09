import { RefreshCw } from "lucide-react";
import { useRef, useState } from "react";
import { useUpdate } from "../../lib/queries";
import { Button } from "../ui";
import { UpdateDialog } from "./UpdateDialog";
import { chipWords, isWorking } from "./updateInstall";
import { useInstallStatus } from "./useInstallUpdate";

/**
 * "Update and restart" as one button, for any screen with room for it (Settings, About mounts it beside the update
 * notice). It opens the update window, and says how far an update has got while one is under way. It shows nothing
 * when there is no newer version, so a screen never has to decide whether to show it.
 */
export function UpdateNowButton() {
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const info = useUpdate().data;
  const waiting = Boolean(info?.update_available && info.latest);
  const install = useInstallStatus(waiting).data;
  if (!waiting && !isWorking(install)) return null;
  const working = isWorking(install);
  return (
    <>
      <Button
        ref={button}
        size="sm"
        variant={working ? "secondary" : "primary"}
        icon={<RefreshCw className="size-3.5" aria-hidden />}
        onClick={() => setOpen(true)}
      >
        {working ? chipWords(install, info?.latest ?? null) : "Update and restart"}
      </Button>
      <UpdateDialog open={open} onOpenChange={setOpen} fallbackFocus={() => button.current} />
    </>
  );
}
