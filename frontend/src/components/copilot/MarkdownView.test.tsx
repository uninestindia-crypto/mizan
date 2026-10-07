import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Markdown } from "./MarkdownView";

afterEach(cleanup);

// Every source file of the Copilot's screens, read as text, to prove none of them can inject markup.
const sources = import.meta.glob(["./*.ts", "./*.tsx", "!./*.test.ts", "!./*.test.tsx"], {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

describe("drawing a reply", () => {
  it("shows hostile HTML as text and creates no elements from it", () => {
    const hostile = '<script>alert(1)</script><img src=x onerror="alert(1)"><b>bold?</b>';
    const { container } = render(<Markdown text={hostile} />);
    expect(container.querySelector("script, img, b, iframe, style")).toBeNull();
    expect(container.textContent).toContain("<script>alert(1)</script>");
    expect(container.textContent).toContain("<b>bold?</b>");
  });

  it("makes a safe link open in a new tab without handing over the page", () => {
    const { container } = render(<Markdown text="Read [the filing](https://www.example.com/a) now" />);
    const anchor = container.querySelector("a");
    expect(anchor?.getAttribute("href")).toBe("https://www.example.com/a");
    expect(anchor?.getAttribute("target")).toBe("_blank");
    expect(anchor?.getAttribute("rel")).toBe("noopener noreferrer");
    expect(container.textContent).toContain("(example.com)");
  });

  it("makes no link at all from javascript:, data: or plain http addresses", () => {
    const text = "[a](javascript:alert(1)) [b](data:text/html,x) [c](http://example.com) [d](//example.com)";
    const { container } = render(<Markdown text={text} />);
    expect(container.querySelectorAll("a")).toHaveLength(0);
    expect(container.textContent).toContain("[a](javascript:alert(1))");
  });

  it("draws paragraphs, bold and lists", () => {
    const { container } = render(<Markdown text={"Intro **bold** text\n\n- one\n- two"} />);
    expect(container.querySelectorAll("p")).toHaveLength(1);
    expect(container.querySelector("strong")?.textContent).toBe("bold");
    expect([...container.querySelectorAll("li")].map((li) => li.textContent)).toEqual(["one", "two"]);
  });
});

describe("the Copilot's screens", () => {
  it("scans the files it means to scan", () => {
    expect(Object.keys(sources).length).toBeGreaterThan(10);
  });

  it("inserts no markup from a reply or an AI model into the page", () => {
    const forbidden = [/dangerouslySetInnerHTML/, /\.innerHTML\s*=/, /insertAdjacentHTML/, /document\.write/];
    const found = Object.entries(sources).flatMap(([file, text]) =>
      forbidden.filter((pattern) => pattern.test(text)).map((pattern) => `${file}: ${pattern}`),
    );
    expect(found).toEqual([]);
  });
});
