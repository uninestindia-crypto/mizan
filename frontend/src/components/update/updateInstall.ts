// "Update and restart": what the engine reports about an update in progress, and the plain words and rules around it.

export type InstallState = "idle" | "downloading" | "checking" | "installing" | "failed";

/** What GET /api/v2/updates/install answers. `message` is already plain language; show it as it is. */
export interface InstallStatus {
  state: InstallState;
  percent: number | null;
  message: string;
  version: string | null;
}

export const IDLE: InstallStatus = { state: "idle", percent: null, message: "", version: null };

export const INSTALLING_WORDS = "Installing the update. QuantOS will close and open again in a moment.";
export const WINDOWS_NOTE = "Windows may ask you to confirm. That is expected.";

/** The two steps that move on their own and are worth looking at once a second. */
export function isPolling(status: InstallStatus | undefined): boolean {
  return status?.state === "downloading" || status?.state === "checking";
}

/** Any step in which an update is under way, so another press of the button changes nothing. */
export function isWorking(status: InstallStatus | undefined): boolean {
  return isPolling(status) || status?.state === "installing";
}

export function percentOf(status: InstallStatus): number | null {
  const percent = status.percent;
  if (percent === null || !Number.isFinite(percent)) return null;
  return Math.max(0, Math.min(100, Math.round(percent)));
}

/** One sentence for the step, without a percentage (that is shown beside it, so it is not announced every second). */
export function stepWords(status: InstallStatus): string {
  if (status.state === "installing") return status.message || INSTALLING_WORDS;
  if (status.state === "failed") return status.message;
  if (status.state === "checking") return status.message || "Checking that the download is genuine.";
  const named = status.version ? `QuantOS ${status.version}` : "the update";
  return status.message || `Downloading ${named}.`;
}

/** The words on the top bar's update chip: what is under way, or that an update is waiting. */
export function chipWords(status: InstallStatus | undefined, latest: string | null): string {
  const percent = status ? percentOf(status) : null;
  if (status?.state === "downloading") return percent === null ? "Updating" : `Updating ${percent}%`;
  if (status?.state === "checking") return "Checking the update";
  if (status?.state === "installing") return "Installing the update";
  if (status?.state === "failed") return "Update stopped";
  return latest ? `Update available: v${latest}` : "Update available";
}

const LINK = /\[([^\]]*)\]\([^)]*\)/g;
/** The engine keeps this many characters of the notes, so a longer set of notes ends in the middle of a line. */
export const NOTES_LIMIT = 1500;
// The dialog has its own "What is new" heading and title, so the notes' own versions of them are dropped. The install
// and checksum part that every release ends with is for people downloading by hand, and is left out too.
const REPEATS_TITLE = /^\s{0,3}#\s+\S/;
const REPEATS_HEADING = /^\s{0,3}#{1,6}\s*what(?:['\u2019]s| is) new\s*$/i;
const DOWNLOAD_PART = /^\s{0,3}#{1,6}\s*(?:install|checksums?)\b/i;

function plainLine(line: string): string {
  return line
    .replace(/<[^>]+>/g, "")
    .replace(LINK, "$1")
    .replace(/^\s{0,3}#{1,6}\s*/, "")
    .replace(/^(\s*)[-*+]\s+/, "$1• ")
    .replace(/(\*\*|__|`)/g, "")
    .trimEnd();
}

/**
 * Release notes arrive written for a web page (headings, bullets, links). Shown as plain text: the marks are dropped,
 * a bullet keeps a bullet, a link keeps its words, and long gaps shrink to one blank line.
 */
export function plainNotes(notes: string | null | undefined): string {
  if (!notes) return "";
  const lines = notes.replace(/\r\n?/g, "\n").split("\n");
  const download = lines.findIndex((line) => DOWNLOAD_PART.test(line));
  const complete = download >= 0 ? lines.slice(0, download) : closeOff(lines, notes.length);
  const kept = complete.filter((line) => !REPEATS_TITLE.test(line) && !REPEATS_HEADING.test(line));
  return kept.map(plainLine).join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

/** Notes cut off at the engine's limit end mid-line: drop that line and say there is more. */
function closeOff(lines: string[], length: number): string[] {
  return length >= NOTES_LIMIT ? [...lines.slice(0, -1), "…"] : lines;
}
