// Safe reading of an agent's reply. The engine promises only paragraphs, bold, "-" lists and https links; this reads
// exactly that and builds plain data (never HTML), so a reply cannot add markup, scripts or styles to the page.

export type Inline =
  | { kind: "text"; text: string }
  | { kind: "bold"; text: string }
  | { kind: "link"; text: string; href: string };

export type Block =
  | { kind: "paragraph"; lines: Inline[][] }
  | { kind: "list"; items: Inline[][] }
  | { kind: "heading"; content: Inline[] };

const MAX_PARSED_LINE = 5_000;
const MAX_LINK_TEXT = 200;
const MAX_URL = 2_048;

/** An https:// address that is safe to open, in its cleaned-up form, or null. Nothing else is ever a link. */
export function safeHttpsUrl(raw: string): string | null {
  if (!/^https:\/\//i.test(raw) || /[\s\u0000-\u001f\u007f<>"'`\\]/.test(raw)) return null;
  try {
    const url = new URL(raw);
    return url.protocol === "https:" && url.hostname && !url.username && !url.password ? url.href : null;
  } catch {
    return null;
  }
}

/** The site a link goes to, shown beside the link's own words so the words cannot hide where it leads. */
export function hostOf(href: string): string {
  try {
    return new URL(href).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

interface Read {
  node: Inline;
  end: number;
}

function readBold(line: string, start: number): Read | null {
  const close = line.indexOf("**", start + 2);
  const text = close < 0 ? "" : line.slice(start + 2, close);
  return text.trim() ? { node: { kind: "bold", text }, end: close + 2 } : null;
}

interface Span {
  /** The character that closes it. */
  end: string;
  /** How far ahead to look, so a hostile line cannot make the search slow. */
  limit: number;
  /** A character that means it is not this kind of span after all. */
  stop: RegExp;
}

const LINK_TEXT: Span = { end: "]", limit: MAX_LINK_TEXT, stop: /\[/ };
const LINK_URL: Span = { end: ")", limit: MAX_URL, stop: /\s/ };

/** The text from `from` up to the span's closing character, or null when it does not close in time or breaks a rule. */
function readUntil(line: string, from: number, span: Span): string | null {
  const close = line.indexOf(span.end, from);
  if (close < 0 || close - from > span.limit) return null;
  const inner = line.slice(from, close);
  return span.stop.test(inner) ? null : inner;
}

function readLink(line: string, start: number): Read | null {
  const text = readUntil(line, start + 1, LINK_TEXT);
  if (!text?.trim() || line[start + text.length + 2] !== "(") return null;
  const urlStart = start + text.length + 3;
  const raw = readUntil(line, urlStart, LINK_URL);
  const href = raw === null ? null : safeHttpsUrl(raw);
  return href === null || raw === null ? null : { node: { kind: "link", text, href }, end: urlStart + raw.length + 1 };
}

/** Bold and links only; everything else, including angle brackets, stays plain text. */
export function parseInline(line: string): Inline[] {
  if (line.length > MAX_PARSED_LINE) return [{ kind: "text", text: line }];
  const out: Inline[] = [];
  let plain = "";
  for (let i = 0; i < line.length; ) {
    const found = line.startsWith("**", i) ? readBold(line, i) : line[i] === "[" ? readLink(line, i) : null;
    if (!found) {
      plain += line[i];
      i += 1;
      continue;
    }
    if (plain) out.push({ kind: "text", text: plain });
    plain = "";
    out.push(found.node);
    i = found.end;
  }
  if (plain) out.push({ kind: "text", text: plain });
  return out;
}

interface Raw {
  kind: "paragraph" | "list" | "heading";
  lines: string[];
}

function lineKind(line: string): { kind: Raw["kind"]; text: string } {
  const heading = /^#{1,6}\s+(.*)$/.exec(line)?.[1];
  if (heading !== undefined) return { kind: "heading", text: heading };
  const item = /^[-*•]\s+(.*)$/.exec(line)?.[1];
  return item !== undefined ? { kind: "list", text: item } : { kind: "paragraph", text: line };
}

function splitBlocks(markdown: string): Raw[] {
  const blocks: Raw[] = [];
  let current: Raw | null = null;
  for (const raw of markdown.replace(/\r\n?/g, "\n").split("\n")) {
    const line = raw.trim();
    if (!line) {
      current = null;
      continue;
    }
    const { kind, text } = lineKind(line);
    const block: Raw = current?.kind === kind && kind !== "heading" ? current : { kind, lines: [] };
    if (block !== current) blocks.push(block);
    block.lines.push(text);
    current = kind === "heading" ? null : block;
  }
  return blocks;
}

function toBlock(raw: Raw): Block {
  if (raw.kind === "heading") return { kind: "heading", content: [{ kind: "bold", text: raw.lines.join(" ") }] };
  const parsed = raw.lines.map(parseInline);
  return raw.kind === "list" ? { kind: "list", items: parsed } : { kind: "paragraph", lines: parsed };
}

/**
 * Turns a reply into blocks: paragraphs, `-` lists, and `#` headings shown as bold lines. It builds data, never HTML,
 * so a reply cannot add markup, scripts or styles to the page.
 */
export function parseReply(markdown: string): Block[] {
  return splitBlocks(markdown).map(toBlock);
}
