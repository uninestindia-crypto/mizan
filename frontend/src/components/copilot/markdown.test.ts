import { describe, expect, it } from "vitest";
import { type Inline, parseInline, parseMarkdown, safeLink } from "./markdown";

const links = (nodes: readonly Inline[]): Inline[] => nodes.filter((n) => n.type === "link");
function flatOne(node: Inline): string {
  if (node.type === "text" || node.type === "link") return node.text;
  return node.type === "bold" ? flat(node.children) : "\n";
}
const flat = (nodes: readonly Inline[]): string => nodes.map(flatOne).join("");

describe("reading a reply", () => {
  it("splits paragraphs on blank lines and keeps single line breaks", () => {
    const blocks = parseMarkdown("First line\nsecond line\n\nNew paragraph");
    expect(blocks).toHaveLength(2);
    expect(blocks[0]).toEqual({
      type: "paragraph",
      children: [{ type: "text", text: "First line" }, { type: "break" }, { type: "text", text: "second line" }],
    });
  });

  it("makes one list from consecutive dash lines", () => {
    const blocks = parseMarkdown("Facts:\n- one\n- **two**\n- three\n\nDone");
    expect(blocks.map((b) => b.type)).toEqual(["paragraph", "list", "paragraph"]);
    const list = blocks[1];
    expect(list?.type === "list" && list.items).toHaveLength(3);
    const bold = { type: "bold", children: [{ type: "text", text: "two" }] };
    expect(list?.type === "list" && list.items[1]).toEqual([bold]);
  });

  it("reads bold, including around a link", () => {
    const nodes = parseInline("This is **very [good](https://example.com/a)** news");
    expect(nodes.map((n) => n.type)).toEqual(["text", "bold", "text"]);
    const bold = nodes[1];
    expect(bold?.type === "bold" && links(bold.children)).toHaveLength(1);
  });

  it("leaves unmatched marks as the text they were", () => {
    expect(flat(parseInline("2 ** 3"))).toBe("2 ** 3");
    expect(flat(parseInline("**open"))).toBe("**open");
    expect(flat(parseInline("****"))).toBe("****");
    expect(flat(parseInline("[not a link]"))).toBe("[not a link]");
  });

  it("copes with Windows line endings and an empty reply", () => {
    expect(parseMarkdown("a\r\n\r\nb")).toHaveLength(2);
    expect(parseMarkdown("")).toEqual([]);
    expect(parseMarkdown("\n\n  \n")).toEqual([]);
  });

  it("does not turn other markdown into anything: headings and numbers stay text", () => {
    const blocks = parseMarkdown("# Heading\n1. one");
    expect(blocks).toHaveLength(1);
    expect(blocks[0]?.type === "paragraph" && flat(blocks[0].children)).toBe("# Heading\n1. one");
  });
});

describe("links", () => {
  it("makes a link only from an https address", () => {
    const [node] = links(parseInline("See [the filing](https://www.example.com/path?a=1)"));
    expect(node).toEqual({
      type: "link",
      text: "the filing",
      href: "https://www.example.com/path?a=1",
      host: "example.com",
    });
  });

  it("shows hostile and non-https links as plain text, never as a link", () => {
    const hostile = [
      "[click](javascript:alert(1))",
      "[click](JAVASCRIPT:alert(1))",
      "[click](data:text/html;base64,PHNjcmlwdD4=)",
      "[click](http://example.com)",
      "[click](//example.com)",
      "[click](/relative/path)",
      "[click](vbscript:msgbox)",
      "[click](https://user:pass@example.com)",
      "[click](https://)",
      "[click]( https://example.com)",
      "[click](https://exa mple.com)",
    ];
    for (const text of hostile) {
      const nodes = parseInline(text);
      expect(links(nodes), text).toEqual([]);
      expect(flat(nodes), text).toBe(text);
    }
  });

  it("does not let a trusted looking address hide a different destination", () => {
    const [node] = links(parseInline("[https://www.mybank.com](https://evil.example/login)"));
    expect(node).toMatchObject({ href: "https://evil.example/login", host: "evil.example" });
  });

  it("keeps nested brackets from building a link to the outer address", () => {
    const nodes = parseInline("[[inner](https://a.example)](https://b.example)");
    const found = links(nodes);
    expect(found).toHaveLength(1);
    expect(found[0]).toMatchObject({ href: "https://a.example/" });
    expect(flat(nodes)).toContain("](https://b.example)");
  });

  it("refuses an address with embedded sign-in details", () => {
    expect(safeLink("https://user:pass@example.com/")).toBeNull();
    expect(safeLink("https://user@example.com/")).toBeNull();
    expect(safeLink("https://example.com/")).not.toBeNull();
  });
});

describe("hostile text", () => {
  it("keeps HTML as ordinary text for the screen to escape", () => {
    const source = '<script>alert(1)</script> <img src=x onerror=alert(1)> <a href="javascript:x">y</a>';
    const blocks = parseMarkdown(source);
    expect(blocks).toEqual([{ type: "paragraph", children: [{ type: "text", text: source }] }]);
  });

  it("does not hang on pathological input", () => {
    const started = Date.now();
    parseMarkdown("[".repeat(20_000));
    parseMarkdown("**a ".repeat(5_000));
    parseMarkdown("[a](".repeat(5_000));
    parseMarkdown(`[${"a".repeat(30_000)}`);
    expect(Date.now() - started).toBeLessThan(2_000);
  });
});
