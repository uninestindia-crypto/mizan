// Plain words for the model details an AI app reports: how hard it thinks, how much it can read, when it came out.

const LEVEL_WORDS: Record<string, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  xhigh: "Extra high",
  max: "Maximum",
  ultra: "Ultra",
};

/** A thinking level in the words a person uses. An unknown level is shown capitalised, never hidden. */
export function thinkingWords(level: string): string {
  return LEVEL_WORDS[level] ?? level.charAt(0).toUpperCase() + level.slice(1);
}

const WORDS_PER_TOKEN = 0.75;

/** "Reads about 2,04,000 words at once", from a size in tokens. Null when the size is not known. */
export function readSizeWords(tokens: number | null | undefined): string | null {
  if (typeof tokens !== "number" || !Number.isFinite(tokens) || tokens <= 0) return null;
  const words = Math.round((tokens * WORDS_PER_TOKEN) / 1000) * 1000;
  return `Reads about ${words.toLocaleString("en-IN")} words at once`;
}

/** "Released 1 Jan 2100" from a YYYY-MM-DD day. Null when there is no usable day. */
export function releasedWords(day: string | null | undefined): string | null {
  if (!day || !/^\d{4}-\d{2}-\d{2}$/.test(day)) return null;
  const parsed = new Date(`${day}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return null;
  const text = parsed.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  return `Released ${text}`;
}

const VERSION_NUMBER = /\d+(?:\.\d+)+/;

/** The version number a person recognises: "codex-cli 0.162.1" becomes "0.162.1". Null when there is none. */
export function versionNumber(text: string | null | undefined): string | null {
  if (!text) return null;
  return VERSION_NUMBER.exec(text)?.[0] ?? null;
}
