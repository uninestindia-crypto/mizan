import { describe, expect, it } from "vitest";
import { hostOf, parseInline, parseReply, safeHttpsUrl } from "./replyMarkdown";

const text = (value: string) => ({ kind: "text", text: value });
const bold = (value: string) => ({ kind: "bold", text: value });
const link = (value: string, href: string) => ({ kind: "link", text: value, href });

describe("reading a reply into blocks", () => {
  it("splits paragraphs on blank lines and keeps line breaks inside one", () => {
    const blocks = parseReply("First line\nsecond line\n\nNext paragraph");
    expect(blocks).toEqual([
      { kind: "paragraph", lines: [[text("First line")], [text("second line")]] },
      { kind: "paragraph", lines: [[text("Next paragraph")]] },
    ]);
  });

  it("reads a dash list, and a list that sits between paragraphs", () => {
    const blocks = parseReply("Before\n- one\n- two\nAfter");
    expect(blocks.map((b) => b.kind)).toEqual(["paragraph", "list", "paragraph"]);
    expect(blocks[1]).toEqual({ kind: "list", items: [[text("one")], [text("two")]] });
  });

  it("does not mistake bold at the start of a line, or a minus sign, for a list", () => {
    expect(parseReply("**Bold** first")[0]?.kind).toBe("paragraph");
    expect(parseReply("-5% today")[0]?.kind).toBe("paragraph");
    expect(parseReply("-")[0]?.kind).toBe("paragraph");
  });

  it("shows a heading as a bold line", () => {
    expect(parseReply("## Summary\nText")).toEqual([
      { kind: "heading", content: [bold("Summary")] },
      { kind: "paragraph", lines: [[text("Text")]] },
    ]);
  });

  it("copes with Windows line endings, extra blank lines and an empty reply", () => {
    expect(parseReply("a\r\n\r\n\r\nb")).toHaveLength(2);
    expect(parseReply("")).toEqual([]);
    expect(parseReply("\n\n  \n")).toEqual([]);
  });
});

describe("reading bold and links in a line", () => {
  it("reads bold text", () => {
    expect(parseInline("a **b** c")).toEqual([text("a "), bold("b"), text(" c")]);
  });

  it("leaves unclosed or empty bold markers as they were written", () => {
    expect(parseInline("a **b c")).toEqual([text("a **b c")]);
    expect(parseInline("a **** b")).toEqual([text("a **** b")]);
    expect(parseInline("a ** ** b")).toEqual([text("a ** ** b")]);
  });

  it("makes a link from an https address only", () => {
    expect(parseInline("see [the filing](https://www.example.com/a?b=1)")).toEqual([
      text("see "),
      link("the filing", "https://www.example.com/a?b=1"),
    ]);
  });

  it("leaves a link that is not safe as plain text", () => {
    const unsafe = [
      "[a](http://example.com)",
      "[a](javascript:alert(1))",
      "[a](JaVaScRiPt:alert(1))",
      "[a](data:text/html,<script>alert(1)</script>)",
      "[a](//example.com)",
      "[a](/relative)",
      "[a](https://" + "someone:" + "word@example.com)", // a link with sign-in details inside it
      "[a](https://example.com/x y)",
      '[a](https://example.com/"onclick="x)',
      "[a](https://example.com/\\@evil.com)",
      "[](https://example.com)",
      "[a]( https://example.com)",
    ];
    for (const line of unsafe) {
      const parts = parseInline(line);
      expect(parts.every((p) => p.kind === "text"), line).toBe(true);
      expect(parts.map((p) => p.text).join(""), line).toBe(line);
    }
  });

  it("keeps markup characters as text", () => {
    const parts = parseInline('<script>alert(1)</script> <img src=x onerror="y"> &amp; **<b>x</b>**');
    expect(parts.map((p) => p.kind)).toEqual(["text", "bold"]);
    expect(parts[0]).toEqual(text('<script>alert(1)</script> <img src=x onerror="y"> &amp; '));
    expect(parts[1]).toEqual(bold("<b>x</b>"));
  });

  it("does not read a link whose words contain another bracket", () => {
    expect(parseInline("[a [b](https://example.com)")).toEqual([text("[a "), link("b", "https://example.com/")]);
  });
});

describe("telling a safe address from an unsafe one", () => {
  it("returns the cleaned-up address for https", () => {
    expect(safeHttpsUrl("https://example.com")).toBe("https://example.com/");
    expect(safeHttpsUrl("HTTPS://Example.com/Path")).toBe("https://example.com/Path");
  });

  it("refuses everything else", () => {
    for (const bad of ["http://example.com", "ftp://x.com", "https:example.com", "https://", "https://:80", "", "x"]) {
      expect(safeHttpsUrl(bad), bad).toBeNull();
    }
    expect(safeHttpsUrl("https://exa\tmple.com")).toBeNull();
    expect(safeHttpsUrl("https://example.com/\u0000")).toBeNull();
  });

  it("names the site a link leads to", () => {
    expect(hostOf("https://www.example.com/a")).toBe("example.com");
    expect(hostOf("https://news.example.org/x")).toBe("news.example.org");
    expect(hostOf("nonsense")).toBe("");
  });
});

describe("hostile or enormous replies", () => {
  it("reads lines built to make a reader slow quickly", () => {
    const patterns = ["[".repeat(4_900), "[a](".repeat(1_200), "**".repeat(2_400)];
    patterns.push("[a]".repeat(1_600), "[x".repeat(2_400));
    const hostile = patterns.flatMap((line) => Array.from({ length: 40 }, () => line)).join("\n");
    const started = performance.now();
    const blocks = parseReply(hostile);
    expect(blocks.length).toBeGreaterThan(0);
    expect(performance.now() - started).toBeLessThan(3_000);
  });

  it("shows a very long line as it is, without trying to read it", () => {
    const long = `**x**${"a".repeat(6_000)}`;
    expect(parseInline(long)).toEqual([text(long)]);
  });

  it("keeps a long reply in full", () => {
    const lines = Array.from({ length: 2_000 }, (_, i) => `- item ${i}`).join("\n");
    const [block] = parseReply(lines);
    expect(block?.kind === "list" && block.items.length).toBe(2_000);
  });
});
