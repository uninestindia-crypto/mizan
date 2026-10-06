// A deliberately tiny, safe reader for the Copilot's replies. It understands only what the engine promises to send:
// paragraphs, **bold**, "- " lists and [text](https://...) links. Everything else, including any HTML, comes out as
// plain text. The result is a plain data tree that the screen turns into elements; no markup string is ever built.

export type Inline =
  | { type: "text"; text: string }
  | { type: "bold"; children: Inline[] }
  | { type: "link"; text: string; href: string; host: string }
  | { type: "break" };

export type Block = { type: "paragraph"; children: Inline[] } | { type: "list"; items: Inline[][] };

export interface SafeLink {
  href: string;
  host: string;
}

/** A link is safe only when it is an https address with a host and no embedded sign-in details. */
export function safeLink(url: string): SafeLink | null {
  if (!url.startsWith("https://")) return null;
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }
  if (parsed.protocol !== "https:" || !parsed.hostname || parsed.username || parsed.password) return null;
  return { href: parsed.href, host: parsed.hostname.replace(/^www\./, "") };
}

const LINK = /\[([^[\]]{1,200})\]\(([^\s()]{1,500})\)/y;

function readLink(text: string, at: number): { node: Inline; end: number } | null {
  LINK.lastIndex = at;
  const match = LINK.exec(text);
  const safe = match?.[2] ? safeLink(match[2]) : null;
  if (!match || !safe) return null;
  return { node: { type: "link", text: match[1] ?? "", ...safe }, end: LINK.lastIndex };
}

function readBold(text: string, at: number): { node: Inline; end: number } | null {
  if (!text.startsWith("**", at)) return null;
  const close = text.indexOf("**", at + 2);
  if (close <= at + 2) return null;
  return { node: { type: "bold", children: parseInline(text.slice(at + 2, close), false) }, end: close + 2 };
}

/** Bold and links, left to right. Anything that does not read cleanly stays as the text it was. */
export function parseInline(text: string, allowBold = true): Inline[] {
  const out: Inline[] = [];
  let plain = "";
  let i = 0;
  while (i < text.length) {
    const found = (allowBold ? readBold(text, i) : null) ?? (text[i] === "[" ? readLink(text, i) : null);
    if (!found) {
      plain += text.charAt(i);
      i += 1;
      continue;
    }
    if (plain) out.push({ type: "text", text: plain });
    plain = "";
    out.push(found.node);
    i = found.end;
  }
  if (plain) out.push({ type: "text", text: plain });
  return out;
}

const LIST_ITEM = /^ {0,3}-\s+(.*)$/;

function paragraph(lines: string[]): Block {
  const children = lines.flatMap((line, index): Inline[] => [
    ...(index > 0 ? [{ type: "break" } as const] : []),
    ...parseInline(line),
  ]);
  return { type: "paragraph", children };
}

/** Blocks of text separated by blank lines; consecutive "- " lines make one list. */
export function parseMarkdown(source: string): Block[] {
  const blocks: Block[] = [];
  let lines: string[] = [];
  let items: Inline[][] = [];
  const endParagraph = () => {
    if (lines.length > 0) blocks.push(paragraph(lines));
    lines = [];
  };
  const endList = () => {
    if (items.length > 0) blocks.push({ type: "list", items });
    items = [];
  };
  for (const line of source.replace(/\r\n?/g, "\n").split("\n")) {
    const item = LIST_ITEM.exec(line);
    if (line.trim() === "") {
      endParagraph();
      endList();
    } else if (item) {
      endParagraph();
      if (item[1]?.trim()) items.push(parseInline(item[1].trim()));
    } else {
      endList();
      lines.push(line.trim());
    }
  }
  endParagraph();
  endList();
  return blocks;
}
