// Indian formatting: ₹ with lakh/crore grouping, signed percentages, short dates.

const cache = new Map<string, Intl.NumberFormat>();

function fmt(options: Intl.NumberFormatOptions): Intl.NumberFormat {
  const key = JSON.stringify(options);
  let formatter = cache.get(key);
  if (!formatter) {
    formatter = new Intl.NumberFormat("en-IN", options);
    cache.set(key, formatter);
  }
  return formatter;
}

const isNum = (v: number | null | undefined): v is number => typeof v === "number" && Number.isFinite(v);

export const DASH = "—";

export function inr(value: number | null | undefined, digits = 2): string {
  if (!isNum(value)) return DASH;
  return fmt({ style: "currency", currency: "INR", minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
}

/** ₹12.34 Cr / ₹5.60 L / ₹8,450 — the way Indian investors read large amounts. */
export function inrCompact(value: number | null | undefined): string {
  if (!isNum(value)) return DASH;
  const abs = Math.abs(value);
  const sign = value < 0 ? "−" : "";
  if (abs >= 1e7) return `${sign}₹${fmt({ maximumFractionDigits: 2, minimumFractionDigits: 2 }).format(abs / 1e7)} Cr`;
  if (abs >= 1e5) return `${sign}₹${fmt({ maximumFractionDigits: 2, minimumFractionDigits: 2 }).format(abs / 1e5)} L`;
  return `${sign}₹${fmt({ maximumFractionDigits: 0 }).format(abs)}`;
}

export function num(value: number | null | undefined, digits = 2): string {
  if (!isNum(value)) return DASH;
  return fmt({ minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
}

export function int(value: number | null | undefined): string {
  if (!isNum(value)) return DASH;
  return fmt({ maximumFractionDigits: 0 }).format(value);
}

/** Fraction to percentage. signed=true prefixes + for gains. */
export function pct(value: number | null | undefined, digits = 1, signed = true): string {
  if (!isNum(value)) return DASH;
  const text = fmt({ minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Math.abs(value) * 100);
  if (value > 0 && signed) return `+${text}%`;
  if (value < 0) return `−${text}%`;
  return `${text}%`;
}

/** Signed rupee change: +₹1,234 / −₹560. */
export function inrSigned(value: number | null | undefined, digits = 0): string {
  if (!isNum(value)) return DASH;
  const body = inr(Math.abs(value), digits);
  if (value > 0) return `+${body}`;
  if (value < 0) return `−${body}`;
  return body;
}

export type Tone = "up" | "down" | "flat";

export function tone(value: number | null | undefined): Tone {
  if (!isNum(value) || value === 0) return "flat";
  return value > 0 ? "up" : "down";
}

export function date(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** Calendar days from an ISO date to today (local). */
export function daysSince(iso: string | null | undefined, today: Date = new Date()): number | null {
  if (!iso) return null;
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(d.getTime())) return null;
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((start.getTime() - d.getTime()) / 86_400_000);
}

/** "3 days old", "4 months old", "5 years old" — never "2016 days old". */
export function ageLabel(days: number): string {
  if (days < 60) return `${days} day${days === 1 ? "" : "s"} old`;
  if (days < 730) return `${Math.round(days / 30)} months old`;
  return `${Math.round(days / 365)} years old`;
}

export function plural(n: number, word: string, many = `${word}s`): string {
  return `${int(n)} ${n === 1 ? word : many}`;
}
